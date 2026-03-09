"""Pair selection and research engine."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Deque, Dict, Optional
from uuid import uuid4

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfig, RuntimeConfigManager
from app.domain import streams
from app.domain.events import MarketSnapshot, RejectedHypothesis, TradeHypothesis
from app.exchange.bybit import BybitClient
from app.infrastructure.event_bus import EventBus
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState


class ResearchEngine:
    """Consumes market snapshots and produces trade hypotheses."""

    def __init__(
        self,
        bus: EventBus,
        store: GlobalAppState,
        notifier: BroadcastManager,
        config_manager: RuntimeConfigManager,
    ) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._bus = bus
        self._store = store
        self._notifier = notifier
        self._client = BybitClient()
        self._last_processed: Dict[str, float] = {}
        self._recent_emit: Deque[float] = deque(maxlen=600)
        self._config_manager = config_manager
        self._config: RuntimeConfig = RuntimeConfig.from_settings(self._settings)

    async def run(self, stop_event: asyncio.Event) -> None:
        try:
            async for message in self._bus.listen(
                streams.MARKET_SNAPSHOTS,
                group="research",
                event_type=MarketSnapshot,
                stop_event=stop_event,
            ):
                snapshot = message.payload
                self._config = await self._config_manager.get_config()
                try:
                    await self._handle_snapshot(snapshot)
                except Exception as exc:  # noqa: BLE001
                    self._logger.exception(
                        "research_engine_error", symbol=snapshot.symbol, error=str(exc)
                    )
                finally:
                    await self._bus.ack(message.stream, "research", message.message_id)
                if stop_event.is_set():
                    break
        finally:
            await self._client.close()

    async def _handle_snapshot(self, snapshot: MarketSnapshot) -> None:
        if snapshot.category not in {snapshot.category.CANDIDATE}:
            return

        denylist = {
            symbol.strip().upper()
            for symbol in (self._config.symbol_denylist or [])
            if symbol and symbol.strip()
        }
        if snapshot.symbol.strip().upper() in denylist:
            return

        timestamp = snapshot.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        snap_ts = timestamp.timestamp()
        last_ts = self._last_processed.get(snapshot.symbol)
        if (
            last_ts
            and snap_ts - last_ts < self._config.research_refresh_interval_seconds
        ):
            return

        if not self._can_emit(snap_ts):
            self._logger.debug("research_throttled", symbol=snapshot.symbol)
            return

        self._last_processed[snapshot.symbol] = snap_ts

        hypothesis = await self._build_hypothesis(snapshot)
        if hypothesis is None:
            rejection = RejectedHypothesis(
                hypothesis_id=f"rej-{uuid4().hex}",
                symbol=snapshot.symbol,
                created_at=datetime.now(timezone.utc),
                reasons=["insufficient edge"],
            )
            await self._bus.publish(streams.RESEARCH_REJECTIONS, rejection)
            await self._store.record_rejection(rejection)
            await self._notifier.broadcast(await self._store.build_dashboard_state())
            return

        await self._bus.publish(streams.RESEARCH_HYPOTHESES, hypothesis)
        await self._notifier.broadcast(await self._store.build_dashboard_state())

    def _can_emit(self, current_ts: float) -> bool:
        max_per_minute = self._config.research_max_hypotheses_per_minute
        if max_per_minute <= 0:
            return True

        while self._recent_emit and current_ts - self._recent_emit[0] > 60.0:
            self._recent_emit.popleft()

        if len(self._recent_emit) >= max_per_minute:
            return False

        self._recent_emit.append(current_ts)
        return True

    async def _build_hypothesis(
        self, snapshot: MarketSnapshot
    ) -> Optional[TradeHypothesis]:
        metrics = snapshot.metrics

        risk_budget = await self._store.get_risk_budget()
        symbol_key = snapshot.symbol.upper()
        portfolio_limit = (
            self._safe_float(risk_budget.get("portfolio_limit")) if risk_budget else 0.0
        )
        symbol_limits = (risk_budget or {}).get("symbol_limits") or {}
        symbol_limit = (
            self._safe_float(symbol_limits.get(symbol_key)) if symbol_limits else 0.0
        )

        try:
            filters = await self._client.get_symbol_filters(snapshot.symbol)
        except Exception as exc:  # noqa: BLE001
            self._logger.debug(
                "symbol_filters_failed", symbol=snapshot.symbol, error=str(exc)
            )
            return None

        tick_size = filters.tick_size if filters.tick_size > 0 else Decimal("0.01")

        snapshot_price = metrics.get("last_price") or 0.0
        ticker_price_dec: Decimal | None = None
        try:
            ticker = await self._client.get_symbol_ticker(snapshot.symbol)
            if ticker.last_price > 0:
                ticker_price_dec = self._quantize_decimal(
                    Decimal(str(ticker.last_price)), tick_size
                )
        except Exception as exc:  # noqa: BLE001
            self._logger.debug(
                "ticker_fetch_failed", symbol=snapshot.symbol, error=str(exc)
            )

        source_price = ticker_price_dec or Decimal(str(snapshot_price))
        if source_price <= 0:
            self._logger.debug("skip_snapshot_invalid_price", symbol=snapshot.symbol)
            return None

        entry_price_dec = self._quantize_decimal(source_price, tick_size)
        base_price_dec = ticker_price_dec or entry_price_dec

        confidence = min(1.0, max(0.0, snapshot.market_score / 100))
        if confidence < self._config.min_confidence_threshold:
            return None

        price_pct = metrics.get("price_24h_pct", 0.0)
        direction = "long" if price_pct >= 0 else "short"
        entry_price = float(entry_price_dec)

        stop_pct_dec = Decimal(str(self._config.default_stop_loss_pct))
        take_pct_dec = Decimal(str(self._config.default_take_profit_pct))
        one = Decimal("1")

        if direction == "long":
            stop_price_dec = entry_price_dec * (one - stop_pct_dec)
            target_price_dec = entry_price_dec * (one + take_pct_dec)
        else:
            stop_price_dec = entry_price_dec * (one + stop_pct_dec)
            target_price_dec = entry_price_dec * (one - take_pct_dec)

        stop_price_dec = self._quantize_decimal(stop_price_dec, tick_size)
        target_price_dec = self._quantize_decimal(target_price_dec, tick_size)

        stop_price_dec = self._ensure_stop_distance(
            direction, entry_price_dec, stop_price_dec, tick_size
        )
        target_price_dec = self._ensure_target_distance(
            direction, entry_price_dec, target_price_dec, tick_size
        )

        stop_price_dec = self._ensure_stop_vs_base(
            direction,
            entry_price_dec,
            stop_price_dec,
            base_price_dec,
            tick_size,
        )
        target_price_dec = self._ensure_target_vs_base(
            direction,
            entry_price_dec,
            target_price_dec,
            base_price_dec,
            tick_size,
        )

        if stop_price_dec <= 0 or target_price_dec <= 0:
            self._logger.debug(
                "invalid_prices", symbol=snapshot.symbol, direction=direction
            )
            return None

        stop_price = float(stop_price_dec)
        target_price = float(target_price_dec)

        base_portfolio_limit = self._config.max_portfolio_exposure_usdt
        effective_portfolio_limit = (
            portfolio_limit if portfolio_limit > 0 else base_portfolio_limit
        )
        max_symbol_alloc = (
            symbol_limit
            if symbol_limit > 0
            else effective_portfolio_limit * self._config.max_symbol_allocation_pct
        )
        derived_cap = (
            effective_portfolio_limit / 3
            if effective_portfolio_limit > 0
            else base_portfolio_limit / 3
        )
        notional = min(
            max_symbol_alloc, derived_cap if derived_cap > 0 else max_symbol_alloc
        )
        notional = max(notional, self._config.min_trade_notional_usdt)
        if entry_price <= 0:
            return None
        position_size = round(notional / entry_price, 3)
        leverage = min(self._config.max_leverage, 3.0)

        if position_size <= 0:
            return None

        hypothesis = TradeHypothesis(
            hypothesis_id=f"hyp-{uuid4().hex}",
            symbol=snapshot.symbol,
            created_at=datetime.now(timezone.utc),
            hypothesis_type=self._classify_setup(snapshot),
            confidence=confidence,
            direction=direction,
            entry_price=round(entry_price, 6),
            target_price=round(target_price, 6),
            stop_price=round(stop_price, 6),
            position_size=position_size,
            leverage=leverage,
            notional_usdt=round(notional, 2),
            supporting_metrics=metrics,
            notes=snapshot.rationale,
        )
        return hypothesis

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _quantize_decimal(value: Decimal, tick_size: Decimal) -> Decimal:
        if tick_size <= 0:
            return value
        return value.quantize(tick_size, rounding=ROUND_HALF_UP)

    @staticmethod
    def _ensure_stop_distance(
        direction: str, entry: Decimal, stop: Decimal, tick_size: Decimal
    ) -> Decimal:
        if tick_size <= 0:
            return stop
        if direction == "long" and stop >= entry:
            adjusted = entry - tick_size
            return adjusted if adjusted > 0 else stop
        if direction == "short" and stop <= entry:
            return entry + tick_size
        return stop

    @staticmethod
    def _ensure_target_distance(
        direction: str, entry: Decimal, target: Decimal, tick_size: Decimal
    ) -> Decimal:
        if tick_size <= 0:
            return target
        if direction == "long" and target <= entry:
            return entry + tick_size
        if direction == "short" and target >= entry:
            adjusted = entry - tick_size
            return adjusted if adjusted > 0 else target
        return target

    @staticmethod
    def _ensure_stop_vs_base(
        direction: str,
        entry: Decimal,
        stop: Decimal,
        base: Decimal,
        tick_size: Decimal,
    ) -> Decimal:
        if tick_size <= 0:
            return stop
        if direction == "long":
            threshold = min(entry, base) - tick_size
            if threshold > 0 and stop >= threshold:
                return threshold
        else:
            threshold = max(entry, base) + tick_size
            if stop <= threshold:
                return threshold
        return stop

    @staticmethod
    def _ensure_target_vs_base(
        direction: str,
        entry: Decimal,
        target: Decimal,
        base: Decimal,
        tick_size: Decimal,
    ) -> Decimal:
        if tick_size <= 0:
            return target
        if direction == "long":
            threshold = max(entry, base) + tick_size
            if target <= threshold:
                return threshold
        else:
            threshold = min(entry, base) - tick_size
            if threshold > 0 and target >= threshold:
                return threshold
        return target

    def _classify_setup(self, snapshot: MarketSnapshot) -> str:
        metrics = snapshot.metrics
        price_pct = metrics.get("price_24h_pct", 0.0)
        funding = metrics.get("funding_rate", 0.0)
        if abs(price_pct) > self._config.volatility_threshold * 3:
            return "momentum" if price_pct > 0 else "liquidation_sweep"
        if abs(funding) > self._config.funding_threshold * 3:
            return "funding_imbalance"
        return "trend" if price_pct > 0 else "mean_reversion"


async def run_research_engine(
    stop_event: asyncio.Event,
    bus: EventBus,
    store: GlobalAppState,
    notifier: BroadcastManager,
    config_manager: RuntimeConfigManager,
) -> None:
    engine = ResearchEngine(bus, store, notifier, config_manager)
    await engine.run(stop_event)
