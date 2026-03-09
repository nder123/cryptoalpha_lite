"""Execution engine responsible for fulfilling CTO-AI directives."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.core.config import get_settings
from app.core.runtime_config import RuntimeConfig, RuntimeConfigManager
from app.core.logging import get_logger
from app.domain import streams
from app.domain.events import CTOAiDecision, ExecutionReport, ExecutionStatus, TradeAction, TradeDirective
from app.exchange.bybit import BybitClient
from app.infrastructure.decision_registry import DecisionRegistry
from app.infrastructure.event_bus import EventBus
from app.state.store import GlobalAppState


class ExecutionEngine:
    """Stateless executor that bridges directives to Bybit orders."""

    def __init__(self, bus: EventBus, config_manager: RuntimeConfigManager, store: GlobalAppState) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._bus = bus
        self._client = BybitClient()
        self._config_manager = config_manager
        self._config: RuntimeConfig = RuntimeConfig.from_settings(self._settings)
        self._decision_registry = DecisionRegistry()
        self._store = store
        self._consecutive_failures = 0
        self._degraded_until: float | None = None
        self._last_health_payload: dict[str, object] | None = None
        self._leverage_cache: dict[str, float] = {}

    async def run(self, stop_event: asyncio.Event) -> None:
        await self._update_health("healthy", message="execution engine started")
        backoff_seconds = 1.0
        try:
            while not stop_event.is_set():
                try:
                    async for message in self._bus.listen(
                        streams.CTOAI_DECISIONS,
                        group="execution",
                        event_type=CTOAiDecision,
                        stop_event=stop_event,
                    ):
                        decision = message.payload
                        self._config = await self._config_manager.get_config()
                        await self._handle_decision(decision)
                        await self._bus.ack(message.stream, "execution", message.message_id)
                        if stop_event.is_set():
                            break

                    backoff_seconds = 1.0
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    self._logger.exception("execution_engine_loop_error", exc_info=exc)
                    await self._update_health("error", reason=str(exc))
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2.0, 30.0)
        finally:
            await self._client.close()
            await self._decision_registry.close()

    async def _handle_decision(self, decision: CTOAiDecision) -> None:
        directive = decision.directive

        if directive is None:
            self._logger.error("execution_decision_missing_directive", decision_uid=decision.decision_uid)
            return

        is_new = await self._decision_registry.register_if_new(decision.decision_uid)
        if not is_new:
            self._logger.warning(
                "execution_duplicate_decision",
                decision_uid=decision.decision_uid,
                directive_id=directive.directive_id,
            )
            await self._emit_report(
                directive,
                ExecutionStatus.REJECTED,
                notes=["duplicate decision", f"decision_uid={decision.decision_uid}"],
            )
            return

        bypass_degraded = decision.source == "operator"
        if self._degraded_until is not None and not bypass_degraded:
            now = time.monotonic()
            if now >= self._degraded_until:
                self._degraded_until = None
                self._consecutive_failures = 0
                await self._update_health("healthy", message="degraded window elapsed")
            else:
                remaining = max(0.0, self._degraded_until - now)
                await self._emit_report(
                    directive,
                    ExecutionStatus.DEGRADED,
                    notes=[
                        "execution degraded",
                        f"decision_uid={decision.decision_uid}",
                        f"retry_after={remaining:.1f}s",
                    ],
                )
                await self._decision_registry.mark_processed(decision.decision_uid)
                await self._update_health(
                    "degraded",
                    remaining_seconds=round(remaining, 2),
                    decision_id=directive.directive_id,
                )
                return

        if directive.action not in {TradeAction.OPEN, TradeAction.CLOSE}:
            await self._emit_report(
                directive,
                ExecutionStatus.REJECTED,
                notes=[f"unsupported action: {directive.action}", f"decision_uid={decision.decision_uid}"]
            )
            await self._decision_registry.mark_processed(decision.decision_uid)
            return

        now_utc = datetime.now(timezone.utc)
        expires_at = directive.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now_utc:
                await self._emit_report(
                    directive,
                    ExecutionStatus.CANCELLED,
                    notes=["directive expired", f"decision_uid={decision.decision_uid}"],
                )
                await self._decision_registry.mark_processed(decision.decision_uid)
                return

        if self._config.dry_run:
            await self._emit_report(
                directive,
                ExecutionStatus.SUBMITTED,
                quantity=directive.quantity,
                notes=["dry-run (no exchange order placed)", f"decision_uid={decision.decision_uid}"],
            )
            await self._decision_registry.mark_processed(decision.decision_uid)
            return

        is_close = directive.action is TradeAction.CLOSE
        reduce_only = directive.reduce_only or is_close

        position_idx: int | None = None
        if is_close:
            try:
                positions = await self._client.fetch_positions(symbol=directive.symbol)
            except Exception as exc:  # noqa: BLE001
                self._logger.debug(
                    "execution_close_positions_fetch_failed",
                    directive_id=directive.directive_id,
                    symbol=directive.symbol,
                    error=str(exc),
                )
            else:
                desired_side = "long" if directive.direction == "long" else "short"
                for pos in positions:
                    if (pos.get("symbol") or "").upper() != directive.symbol.upper():
                        continue
                    if (pos.get("side") or "").lower() != desired_side:
                        continue
                    raw_idx = pos.get("position_idx")
                    try:
                        position_idx = int(raw_idx) if raw_idx is not None else None
                    except (TypeError, ValueError):
                        position_idx = None
                    break

        current_exposure = 0.0
        if directive.action is TradeAction.OPEN:
            try:
                positions = await self._client.fetch_positions()
            except Exception as exc:  # noqa: BLE001
                self._logger.error(
                    "execution_exposure_fetch_failed",
                    directive_id=directive.directive_id,
                    symbol=directive.symbol,
                    error=str(exc),
                )
                await self._emit_report(
                    directive,
                    ExecutionStatus.REJECTED,
                    notes=["failed to fetch current exposure", f"decision_uid={decision.decision_uid}"],
                )
                await self._decision_registry.mark_processed(decision.decision_uid)
                return
            current_exposure = sum(abs(float(position.get("notional_usdt") or 0.0)) for position in positions)

        risk_budget: dict[str, object] = {}
        try:
            risk_budget = await self._store.get_risk_budget()
        except Exception as exc:  # noqa: BLE001
            self._logger.debug("execution_risk_budget_unavailable", error=str(exc))

        portfolio_limit = self._safe_float(risk_budget.get("portfolio_limit")) if risk_budget else 0.0
        symbol_limits = (risk_budget or {}).get("symbol_limits") or {}
        symbol_key = directive.symbol.upper()
        symbol_limit = self._safe_float(symbol_limits.get(symbol_key)) if symbol_limits else 0.0

        base_portfolio_limit = self._config.max_portfolio_exposure_usdt
        effective_portfolio_limit = portfolio_limit if portfolio_limit > 0 else base_portfolio_limit
        effective_symbol_limit = symbol_limit if symbol_limit > 0 else (
            effective_portfolio_limit * self._config.max_symbol_allocation_pct
            if effective_portfolio_limit > 0
            else base_portfolio_limit * self._config.max_symbol_allocation_pct
        )

        try:
            if directive.action is TradeAction.OPEN:
                side = "Buy" if directive.direction == "long" else "Sell"
            else:  # CLOSE
                side = "Sell" if directive.direction == "long" else "Buy"

            if directive.action is TradeAction.OPEN and directive.leverage:
                try:
                    await self._ensure_leverage(directive.symbol, directive.leverage)
                except Exception as exc:  # noqa: BLE001
                    self._logger.error(
                        "execution_set_leverage_failed",
                        directive_id=directive.directive_id,
                        symbol=directive.symbol,
                        leverage=directive.leverage,
                        error=str(exc),
                    )
                    await self._emit_report(
                        directive,
                        ExecutionStatus.REJECTED,
                        notes=[
                            "failed to set leverage on exchange",
                            f"leverage={directive.leverage}",
                            str(exc),
                            f"decision_uid={decision.decision_uid}",
                        ],
                    )
                    await self._decision_registry.mark_processed(decision.decision_uid)
                    return

            price_str: str | None = None
            tp_str: str | None = None
            sl_str: str | None = None

            if directive.price is not None:
                price_dec = Decimal(str(directive.price))
                price_str = self._format_decimal(price_dec)

            tp_dec: Decimal | None = None
            sl_dec: Decimal | None = None

            if directive.action is TradeAction.OPEN:
                filters = await self._client.get_symbol_filters(directive.symbol)
                tick_size = filters.tick_size if filters.tick_size > 0 else Decimal("0.01")

                price_for_notional: float | None = directive.price

                if directive.take_profit_price is not None:
                    tp_dec = self._quantize_decimal(Decimal(str(directive.take_profit_price)), tick_size)
                if directive.stop_loss_price is not None:
                    sl_dec = self._quantize_decimal(Decimal(str(directive.stop_loss_price)), tick_size)

                base_price: Decimal | None = None
                market_price: float | None = None
                try:
                    ticker = await self._client.get_symbol_ticker(directive.symbol)
                except Exception as exc:  # noqa: BLE001
                    self._logger.debug("execution_ticker_failed", symbol=directive.symbol, error=str(exc))
                else:
                    if ticker.last_price > 0:
                        base_price = self._quantize_decimal(Decimal(str(ticker.last_price)), tick_size)
                        market_price = float(ticker.last_price)

                if base_price is not None:
                    if directive.direction == "long":
                        if sl_dec is not None and sl_dec >= base_price:
                            adjusted = base_price - tick_size
                            if adjusted <= 0:
                                adjusted = base_price * Decimal("0.99")
                            sl_dec = self._quantize_decimal(max(adjusted, Decimal("0.0001")), tick_size)
                        if tp_dec is not None and tp_dec <= base_price:
                            tp_dec = self._quantize_decimal(base_price + tick_size, tick_size)
                    else:
                        if sl_dec is not None and sl_dec <= base_price:
                            sl_dec = self._quantize_decimal(base_price + tick_size, tick_size)
                        if tp_dec is not None and tp_dec >= base_price:
                            adjusted = base_price - tick_size
                            if adjusted > 0:
                                tp_dec = self._quantize_decimal(adjusted, tick_size)

                entry_dec = Decimal(str(directive.price)) if directive.price is not None else None
                if entry_dec is not None:
                    entry_dec = self._quantize_decimal(entry_dec, tick_size)
                    if directive.direction == "long" and sl_dec is not None and sl_dec >= entry_dec:
                        sl_dec = self._quantize_decimal(entry_dec - tick_size, tick_size)
                    if directive.direction == "short" and sl_dec is not None and sl_dec <= entry_dec:
                        sl_dec = self._quantize_decimal(entry_dec + tick_size, tick_size)

                if price_for_notional is None:
                    if entry_dec is not None:
                        price_for_notional = float(entry_dec)
                    elif base_price is not None:
                        price_for_notional = float(base_price)
                    elif market_price is not None:
                        price_for_notional = market_price

                if price_for_notional is not None:
                    order_notional = price_for_notional * directive.quantity
                    total_exposure = current_exposure + order_notional
                    if effective_portfolio_limit > 0 and total_exposure > effective_portfolio_limit:
                        self._logger.warning(
                            "execution_exposure_limit_exceeded",
                            directive_id=directive.directive_id,
                            symbol=directive.symbol,
                            order_notional=order_notional,
                            current_exposure=current_exposure,
                            limit=effective_portfolio_limit,
                        )
                        await self._emit_report(
                            directive,
                            ExecutionStatus.REJECTED,
                            notes=[
                                "portfolio exposure limit exceeded",
                                f"current={current_exposure:.2f}usdt",
                                f"order={order_notional:.2f}usdt",
                                f"limit={effective_portfolio_limit:.2f}usdt",
                                f"decision_uid={decision.decision_uid}",
                            ],
                        )
                        await self._decision_registry.mark_processed(decision.decision_uid)
                        return

                    if effective_symbol_limit > 0 and order_notional > effective_symbol_limit:
                        self._logger.warning(
                            "execution_symbol_limit_exceeded",
                            directive_id=directive.directive_id,
                            symbol=directive.symbol,
                            order_notional=order_notional,
                            symbol_limit=effective_symbol_limit,
                        )
                        await self._emit_report(
                            directive,
                            ExecutionStatus.REJECTED,
                            notes=[
                                "per-symbol allocation limit exceeded",
                                f"order={order_notional:.2f}usdt",
                                f"symbol_limit={effective_symbol_limit:.2f}usdt",
                                f"decision_uid={decision.decision_uid}",
                            ],
                        )
                        await self._decision_registry.mark_processed(decision.decision_uid)
                        return
                else:
                    self._logger.warning(
                        "execution_exposure_price_unknown",
                        directive_id=directive.directive_id,
                        symbol=directive.symbol,
                    )

                if tp_dec is not None:
                    tp_str = self._format_decimal(tp_dec)
                if sl_dec is not None:
                    sl_str = self._format_decimal(sl_dec)

            attempts = max(0, self._config.execution_retry_attempts)
            attempt = 0
            result = None
            last_error: Exception | None = None
            insufficient_balance_error: str | None = None
            while attempt <= attempts:
                try:
                    result = await self._client.place_order(
                        symbol=directive.symbol,
                        side=side,
                        order_type=directive.order_type.title(),
                        qty=f"{directive.quantity}",
                        price=price_str,
                        time_in_force=directive.time_in_force,
                        reduce_only=reduce_only,
                        position_idx=position_idx,
                        take_profit=tp_str,
                        stop_loss=sl_str,
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    attempt += 1
                    self._logger.error(
                        "execution_order_attempt_failed",
                        directive_id=directive.directive_id,
                        attempt=attempt,
                        max_attempts=attempts + 1,
                        error=str(exc),
                    )
                    error_text = str(exc)
                    if "retCode" in error_text and "110007" in error_text:
                        insufficient_balance_error = error_text
                        break
                    if attempt > attempts:
                        break
                    backoff = max(0.0, self._config.execution_retry_backoff_seconds)
                    if backoff > 0:
                        await asyncio.sleep(backoff * attempt)

            if insufficient_balance_error:
                notes = [
                    "insufficient balance for order",
                    insufficient_balance_error,
                    f"decision_uid={decision.decision_uid}",
                ]
                await self._emit_report(directive, ExecutionStatus.REJECTED, notes=notes)
                await self._decision_registry.mark_processed(decision.decision_uid)
                await self._update_health(
                    "insufficient_balance",
                    reason="Bybit reported insufficient margin",
                    details=insufficient_balance_error,
                )
                return

            if result is None:
                error_message = str(last_error) if last_error else "unknown execution error"
                degraded = await self._register_failure(error_message)
                status = ExecutionStatus.DEGRADED if degraded else ExecutionStatus.FAILED
                await self._emit_report(
                    directive,
                    status,
                    notes=[
                        error_message,
                        f"decision_uid={decision.decision_uid}",
                        f"attempts={attempts + 1}",
                    ],
                )
                await self._decision_registry.mark_processed(decision.decision_uid)
                return
        except Exception as exc:  # noqa: BLE001
            self._logger.error("execution_error", directive_id=directive.directive_id, error=str(exc))
            degraded = await self._register_failure(str(exc))
            status = ExecutionStatus.DEGRADED if degraded else ExecutionStatus.FAILED
            await self._emit_report(
                directive,
                status,
                notes=[str(exc), f"decision_uid={decision.decision_uid}"],
            )
            await self._decision_registry.mark_processed(decision.decision_uid)
            return

        notes = [
            f"order_id={result.order_id}",
            f"status={result.status}",
            f"decision_uid={decision.decision_uid}",
        ]
        await self._emit_report(
            directive,
            ExecutionStatus.SUBMITTED,
            quantity=result.qty,
            notes=notes,
        )
        await self._decision_registry.mark_processed(decision.decision_uid)

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    async def _ensure_leverage(self, symbol: str, leverage: float) -> None:
        target = max(1.0, float(leverage))
        cached = self._leverage_cache.get(symbol)
        if cached is not None and abs(cached - target) <= 1e-6:
            return
        await self._client.set_leverage(symbol, target)
        self._leverage_cache[symbol] = target

    async def _emit_report(
        self,
        directive: TradeDirective,
        status: ExecutionStatus,
        *,
        quantity: Optional[float] = None,
        avg_price: Optional[float] = None,
        fees_paid: Optional[float] = None,
        notes: Optional[list[str]] = None,
    ) -> None:
        report = ExecutionReport(
            directive_id=directive.directive_id,
            symbol=directive.symbol,
            action=directive.action,
            status=status,
            quantity=quantity or 0.0,
            avg_price=avg_price,
            fees_paid=fees_paid,
            reported_at=datetime.now(timezone.utc),
            notes=notes or [],
        )
        await self._bus.publish(streams.EXECUTION_REPORTS, report)

    async def _register_failure(self, reason: str) -> bool:
        self._consecutive_failures += 1
        threshold = max(0, self._config.execution_degraded_threshold)
        cooldown = max(0.0, self._config.execution_degraded_cooldown_seconds)
        degraded = False
        if threshold and self._consecutive_failures >= threshold:
            degraded = True
            self._degraded_until = time.monotonic() + max(cooldown, 10.0)
            await self._update_health(
                "degraded",
                reason=reason,
                cooldown_seconds=max(cooldown, 10.0),
                consecutive_failures=self._consecutive_failures,
            )
        else:
            await self._update_health(
                "unhealthy",
                reason=reason,
                consecutive_failures=self._consecutive_failures,
            )
        return degraded

    async def _register_success(self) -> None:
        self._consecutive_failures = 0
        if self._degraded_until is None:
            await self._update_health("healthy")

    async def _update_health(self, status: str, **details: object) -> None:
        payload: dict[str, object] = {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "exchange_unhealthy": status != "healthy",
        }
        if details:
            payload.update(details)
        if self._last_health_payload == payload:
            return
        self._last_health_payload = payload
        await self._store.set_service_health("execution-engine", payload)

    @staticmethod
    def _quantize_decimal(value: Decimal, tick_size: Decimal) -> Decimal:
        if tick_size <= 0:
            return value
        return value.quantize(tick_size, rounding=ROUND_HALF_UP)

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        normalized = value.normalize()
        formatted = format(normalized, "f")
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted or "0"


async def run_execution_engine(
    stop_event: asyncio.Event,
    bus: EventBus,
    config_manager: RuntimeConfigManager,
    store: GlobalAppState,
) -> None:
    engine = ExecutionEngine(bus, config_manager, store)
    await engine.run(stop_event)
