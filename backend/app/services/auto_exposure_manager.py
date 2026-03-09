from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.exchange.bybit import BybitClient
from app.repositories.runtime_settings import RuntimeSettingsRepository
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState


class AutoExposureManager:
    """Automatically adjusts exposure limits based on Bybit wallet balance."""

    def __init__(
        self,
        config_manager: RuntimeConfigManager,
        settings_repo: RuntimeSettingsRepository,
        store: GlobalAppState,
        notifier: BroadcastManager,
    ) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._config_manager = config_manager
        self._settings_repo = settings_repo
        self._store = store
        self._notifier = notifier
        self._client = BybitClient()
        self._redis = redis.from_url(self._settings.redis_dsn, encoding="utf-8", decode_responses=True)
        self._interval_seconds = 30.0
        self._credentials_missing_logged = False
        self._equity_high_watermark = 0.0
        self._current_guard_state = "normal"
        self._last_volatility_state = "unknown"

    async def run(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                try:
                    await self._tick()
                except Exception as exc:  # noqa: BLE001
                    self._logger.exception("auto_exposure_tick_failed", exc_info=exc)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._interval_seconds)
                except asyncio.TimeoutError:
                    continue
        finally:
            await self._client.close()
            await self._redis.aclose()

    async def _tick(self) -> None:
        config = await self._config_manager.get_config()
        if not config.auto_exposure_enabled:
            self._credentials_missing_logged = False
            return

        if not self._has_credentials():
            await self._handle_missing_credentials()
            return

        wallet_totals = await self._client.fetch_wallet_balance("USDT", "UNIFIED")
        total_equity = self._pick_equity(wallet_totals)
        if total_equity <= 0:
            self._logger.warning("auto_exposure_empty_equity", details=wallet_totals)
            return

        available_equity = self._coerce_float(wallet_totals.get("available_to_withdraw"))
        if available_equity <= 0:
            available_equity = total_equity

        candidates, volatility_index = await self._collect_market_context()
        portfolio_limit, volatility_factor = self._derive_portfolio_limit(config, total_equity, volatility_index)
        portfolio_limit, guard_state, drawdown_pct = self._apply_equity_guard(config, portfolio_limit, total_equity)
        portfolio_limit, volatility_state = self._apply_volatility_guard(config, portfolio_limit, volatility_index, total_equity)
        symbol_limits = self._allocate_symbol_limits(config, portfolio_limit, candidates)

        rounded_total_equity = round(total_equity, 2)
        rounded_portfolio_limit = round(portfolio_limit, 2)
        rounded_available_equity = round(available_equity, 2)
        risk_budget_payload = {
            "portfolio_limit": rounded_portfolio_limit,
            "total_equity": rounded_total_equity,
            "available_equity": rounded_available_equity,
            "volatility_index": round(volatility_index, 6),
            "volatility_factor": round(volatility_factor, 4),
            "symbol_limits": symbol_limits,
            "equity_guard_state": guard_state,
            "equity_drawdown_pct": round(drawdown_pct, 4),
            "volatility_state": volatility_state,
        }

        previous_budget = await self._store.get_risk_budget()
        budget_changed = self._budget_has_changed(previous_budget, risk_budget_payload)
        if budget_changed:
            await self._store.set_risk_budget(risk_budget_payload)

        await self._persist_guard_snapshot(risk_budget_payload)

        updates: Dict[str, Any] = {}
        if abs(config.max_portfolio_exposure_usdt - rounded_portfolio_limit) > 1.0:
            updates["max_portfolio_exposure_usdt"] = rounded_portfolio_limit

        derived_symbol_pct = config.max_symbol_allocation_pct
        if portfolio_limit > 0 and symbol_limits:
            max_symbol_notional = max(symbol_limits.values())
            derived_symbol_pct = min(1.0, max(0.01, max_symbol_notional / portfolio_limit))
            derived_symbol_pct = round(derived_symbol_pct, 4)

        if abs(config.max_symbol_allocation_pct - derived_symbol_pct) > 1e-4:
            updates["max_symbol_allocation_pct"] = derived_symbol_pct

        should_broadcast = budget_changed

        if updates:
            new_config = await self._config_manager.update(updates)
            overrides = await self._config_manager.export_overrides()
            await self._settings_repo.upsert_overrides(overrides)
            await self._store.set_runtime_config(new_config)
            should_broadcast = True
            self._logger.info(
                "auto_exposure_limits_updated",
                total_equity=rounded_total_equity,
                updates=updates,
                volatility_index=risk_budget_payload["volatility_index"],
                volatility_factor=risk_budget_payload["volatility_factor"],
            )
        elif budget_changed:
            self._logger.debug(
                "auto_exposure_budget_updated",
                total_equity=rounded_total_equity,
                portfolio_limit=rounded_portfolio_limit,
                volatility_index=risk_budget_payload["volatility_index"],
                volatility_factor=risk_budget_payload["volatility_factor"],
            )

        if should_broadcast:
            await self._notifier.broadcast(await self._store.build_dashboard_state())

    async def _collect_market_context(self) -> Tuple[List[Tuple[str, Dict[str, Any]]], float]:
        try:
            overview = await self._store.list_market()
        except Exception as exc:  # noqa: BLE001
            self._logger.debug("auto_exposure_market_context_failed", error=str(exc))
            return [], 0.0

        candidates = list(overview.candidate.items())
        if not candidates:
            return [], 0.0

        candidates.sort(key=lambda item: self._coerce_float(item[1].get("score")), reverse=True)
        top_candidates = candidates[: min(len(candidates), 20)]

        volatility_samples = []
        for _, payload in top_candidates:
            metrics = payload.get("metrics") or {}
            sample = abs(self._coerce_float(metrics.get("price_24h_pct")))
            if sample > 0:
                volatility_samples.append(sample)

        volatility_index = sum(volatility_samples) / len(volatility_samples) if volatility_samples else 0.0
        return top_candidates, volatility_index

    def _derive_portfolio_limit(self, config, total_equity: float, volatility_index: float) -> Tuple[float, float]:
        if total_equity <= 0:
            return 0.0, 1.0

        base_target = total_equity * max(config.risk_target_pct, 0.0)
        if base_target <= 0:
            base_target = total_equity * max(config.auto_exposure_portfolio_pct, 0.0)
        base_target = max(config.min_trade_notional_usdt, base_target)

        clamped_vol = max(0.0, min(0.2, volatility_index))
        calm_bonus = max(0.0, 0.03 - clamped_vol) * (1 + config.volatility_sensitivity)
        reduction = clamped_vol * config.volatility_sensitivity * 2
        volatility_factor = max(0.3, min(1.5, 1.0 + calm_bonus - reduction))

        structural_cap = total_equity * max(config.auto_exposure_portfolio_pct, 0.0)
        if structural_cap <= 0:
            structural_cap = total_equity

        raw_limit = base_target * volatility_factor
        raw_limit = min(raw_limit, structural_cap)
        raw_limit = min(raw_limit, total_equity)

        final_limit = max(config.min_trade_notional_usdt, raw_limit)

        manual_cap = AutoExposureManager._coerce_float(getattr(config, "max_portfolio_exposure_usdt", 0.0))
        if manual_cap > 0.0:
            final_limit = min(final_limit, manual_cap)

        return final_limit, volatility_factor

    def _apply_equity_guard(self, config, portfolio_limit: float, total_equity: float) -> Tuple[float, str, float]:
        if total_equity <= 0:
            return config.min_trade_notional_usdt, "halt", 1.0

        if total_equity > self._equity_high_watermark:
            self._equity_high_watermark = total_equity

        drawdown_pct = 0.0
        if self._equity_high_watermark > 0:
            drawdown_pct = max(0.0, (self._equity_high_watermark - total_equity) / self._equity_high_watermark)

        max_daily_loss_pct = getattr(config, "max_daily_loss_pct", 0.03) or 0.03
        caution_threshold = max(0.03, min(0.12, max_daily_loss_pct * 2))
        severe_threshold = max(caution_threshold * 1.5, 0.08)

        state = "normal"
        adjusted_limit = portfolio_limit

        if drawdown_pct >= severe_threshold:
            state = "halt"
            adjusted_limit = min(adjusted_limit, total_equity * 0.1)
        elif drawdown_pct >= caution_threshold:
            state = "caution"
            adjusted_limit = min(adjusted_limit, total_equity * 0.25)

        adjusted_limit = max(config.min_trade_notional_usdt, adjusted_limit)

        if state != self._current_guard_state:
            self._logger.warning(
                "auto_exposure_guard_state",
                state=state,
                drawdown_pct=round(drawdown_pct, 4),
                total_equity=round(total_equity, 2),
            )
            self._current_guard_state = state

        return adjusted_limit, state, drawdown_pct

    def _apply_volatility_guard(
        self,
        config,
        portfolio_limit: float,
        volatility_index: float,
        total_equity: float,
    ) -> Tuple[float, str]:
        state = "calm"
        guard_multiplier = 1.0

        if volatility_index >= 0.12:
            state = "turbulent"
            guard_multiplier = 0.4
        elif volatility_index >= 0.08:
            state = "elevated"
            guard_multiplier = 0.6
        elif volatility_index >= 0.04:
            state = "choppy"
            guard_multiplier = 0.8

        adjusted_limit = portfolio_limit
        if guard_multiplier < 1.0:
            cap = total_equity * guard_multiplier
            adjusted_limit = min(portfolio_limit, cap)
            adjusted_limit = max(config.min_trade_notional_usdt, adjusted_limit)

        if state != self._last_volatility_state:
            self._logger.info(
                "auto_exposure_volatility_state",
                state=state,
                volatility_index=round(volatility_index, 4),
                guard_multiplier=guard_multiplier,
            )
            self._last_volatility_state = state

        return adjusted_limit, state

    async def _persist_guard_snapshot(self, payload: Dict[str, Any]) -> None:
        snapshot = {
            "equity_guard_state": payload.get("equity_guard_state"),
            "volatility_state": payload.get("volatility_state"),
            "equity_drawdown_pct": payload.get("equity_drawdown_pct"),
            "portfolio_limit": payload.get("portfolio_limit"),
            "total_equity": payload.get("total_equity"),
            "available_equity": payload.get("available_equity"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._redis.set("auto_exposure:guard_state", json.dumps(snapshot))
        except Exception as exc:  # noqa: BLE001
            self._logger.debug("auto_exposure_guard_snapshot_failed", error=str(exc))

    def _allocate_symbol_limits(
        self,
        config,
        portfolio_limit: float,
        candidates: List[Tuple[str, Dict[str, Any]]],
    ) -> Dict[str, float]:
        if portfolio_limit <= 0 or not candidates:
            return {}

        weights: Dict[str, float] = {}
        sensitivity = max(config.volatility_sensitivity, 0.1)
        for symbol, payload in candidates:
            score = self._coerce_float(payload.get("score"))
            metrics = payload.get("metrics") or {}
            volatility = abs(self._coerce_float(metrics.get("price_24h_pct")))
            base_weight = max(score, 1.0)
            penalty = 1.0 + (volatility * sensitivity * 10)
            weight = max(base_weight / penalty, 0.1)
            weights[symbol] = weight

        total_weight = sum(weights.values())
        if total_weight <= 0:
            return {}

        cap_ratio = max(config.max_symbol_allocation_pct, 0.01)
        cap_notional = portfolio_limit * cap_ratio
        symbol_limits: Dict[str, float] = {}

        for symbol, weight in weights.items():
            allocation = portfolio_limit * (weight / total_weight)
            allocation = max(allocation, config.min_trade_notional_usdt)
            if cap_notional > 0:
                allocation = min(allocation, cap_notional)
            symbol_limits[symbol] = round(allocation, 2)

        total_assigned = sum(symbol_limits.values())
        if portfolio_limit > 0 and total_assigned > portfolio_limit:
            scale = portfolio_limit / total_assigned
            symbol_limits = {symbol: round(limit * scale, 2) for symbol, limit in symbol_limits.items()}

        return symbol_limits

    @staticmethod
    def _coerce_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _budget_has_changed(previous: Dict[str, Any], current: Dict[str, Any]) -> bool:
        if not previous:
            return True

        for key in ("portfolio_limit", "total_equity", "available_equity"):
            if abs(AutoExposureManager._coerce_float(previous.get(key)) - AutoExposureManager._coerce_float(current.get(key))) > 0.5:
                return True

        prev_limits = previous.get("symbol_limits") or {}
        curr_limits = current.get("symbol_limits") or {}

        if set(prev_limits.keys()) != set(curr_limits.keys()):
            return True

        for symbol, value in curr_limits.items():
            if abs(AutoExposureManager._coerce_float(prev_limits.get(symbol)) - AutoExposureManager._coerce_float(value)) > 0.5:
                return True

        prev_vol_index = AutoExposureManager._coerce_float(previous.get("volatility_index"))
        curr_vol_index = AutoExposureManager._coerce_float(current.get("volatility_index"))
        if abs(prev_vol_index - curr_vol_index) > 0.01:
            return True

        return False

    def _has_credentials(self) -> bool:
        return bool(self._settings.bybit_api_key and self._settings.bybit_api_secret)

    async def _handle_missing_credentials(self) -> None:
        if not self._credentials_missing_logged:
            self._logger.warning("auto_exposure_disabled_no_credentials")
            self._credentials_missing_logged = True

    @staticmethod
    def _pick_equity(payload: Dict[str, float]) -> float:
        candidates = [payload.get("total_equity"), payload.get("available_to_withdraw"), payload.get("wallet_balance")]
        return max(value for value in candidates if isinstance(value, (int, float))) if any(
            isinstance(value, (int, float)) for value in candidates
        ) else 0.0


async def run_auto_exposure_manager(
    stop_event: asyncio.Event,
    config_manager: RuntimeConfigManager,
    settings_repo: RuntimeSettingsRepository,
    store: GlobalAppState,
    notifier: BroadcastManager,
) -> None:
    manager = AutoExposureManager(config_manager, settings_repo, store, notifier)
    await manager.run(stop_event)
