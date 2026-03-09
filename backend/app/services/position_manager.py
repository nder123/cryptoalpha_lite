"""Autonomous position management service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.domain import streams
from app.domain.events import (
    ExecutionReport,
    ExecutionStatus,
    PositionEvent,
    PositionEventType,
    TradeAction,
    TradeDirective,
)
from app.exchange.bybit import BybitClient
from app.infrastructure.event_bus import EventBus
from app.state.cto_ai import CTOAIOrchestrator
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState


@dataclass(slots=True)
class TrackedPosition:
    directive_id: str
    hypothesis_id: Optional[str]
    symbol: str
    direction: str
    quantity: float
    entry_price: Optional[float]
    target_price: Optional[float]
    stop_price: Optional[float]
    opened_at: datetime
    last_update: datetime
    close_requested: bool = False
    last_price_event: datetime | None = None
    last_close_directive_id: str | None = None
    last_close_reason: str | None = None
    last_close_order_type: str | None = None
    last_close_issued_at: datetime | None = None
    last_close_order_id: str | None = None
    last_close_escalated: bool = False


class PositionManager:
    """Automatically supervises open positions and issues closing directives."""

    def __init__(
        self,
        bus: EventBus,
        orchestrator: CTOAIOrchestrator,
        store: GlobalAppState,
        notifier: BroadcastManager,
        config_manager: RuntimeConfigManager,
    ) -> None:
        self._logger = get_logger(__name__)
        self._bus = bus
        self._orchestrator = orchestrator
        self._store = store
        self._notifier = notifier
        self._config_manager = config_manager
        self._directive_cache: Dict[str, TradeDirective] = {}
        self._positions: Dict[str, TrackedPosition] = {}
        self._close_map: Dict[str, str] = {}
        self._client = BybitClient()

    async def run(self, stop_event: asyncio.Event) -> None:
        consumers = [
            asyncio.create_task(self._consume_directives(stop_event)),
            asyncio.create_task(self._consume_execution_reports(stop_event)),
            asyncio.create_task(self._poll_positions(stop_event)),
        ]
        try:
            await asyncio.gather(*consumers)
        except asyncio.CancelledError:
            for task in consumers:
                task.cancel()
            raise
        finally:
            await self._client.close()

    async def _consume_directives(self, stop_event: asyncio.Event) -> None:
        group = "position-manager-directives"
        async for message in self._bus.listen(
            streams.CTOAI_DIRECTIVES,
            group=group,
            event_type=TradeDirective,
            stop_event=stop_event,
        ):
            directive = message.payload
            self._directive_cache[directive.directive_id] = directive
            await self._bus.ack(message.stream, group, message.message_id)
            if stop_event.is_set():
                break

    async def _consume_execution_reports(self, stop_event: asyncio.Event) -> None:
        group = "position-manager-exec"
        async for message in self._bus.listen(
            streams.EXECUTION_REPORTS,
            group=group,
            event_type=ExecutionReport,
            stop_event=stop_event,
        ):
            report = message.payload
            try:
                await self._handle_execution(report)
            except Exception as exc:  # noqa: BLE001
                directive = self._directive_cache.get(report.directive_id)
                self._logger.exception(
                    "position_manager_execution_error",
                    exc_info=exc,
                    directive_id=report.directive_id,
                )
                if directive is not None:
                    await self._publish_event(
                        PositionEventType.ERROR,
                        directive_id=report.directive_id,
                        symbol=directive.symbol,
                        direction=directive.direction,
                        status=report.status.value,
                        notes=[str(exc)],
                        origin_directive_id=self._close_map.get(report.directive_id),
                    )
            finally:
                await self._bus.ack(message.stream, group, message.message_id)
            if stop_event.is_set():
                break

    async def _poll_positions(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._evaluate_positions()
            try:
                config = await self._config_manager.get_config()
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "position_manager_config_unavailable", error=str(exc)
                )
                interval = 10.0
            else:
                interval = max(
                    1.0, float(config.position_manager_poll_interval_seconds)
                )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _handle_execution(self, report: ExecutionReport) -> None:
        directive = self._directive_cache.get(report.directive_id)
        if directive is None:
            self._logger.debug(
                "position_manager_unknown_directive", directive_id=report.directive_id
            )
            return

        action = directive.action
        if action is TradeAction.OPEN:
            if report.status not in {
                ExecutionStatus.FILLED,
                ExecutionStatus.PARTIALLY_FILLED,
            }:
                return
            await self._register_open_fill(directive, report)
        elif action is TradeAction.CLOSE:
            if report.status is ExecutionStatus.SUBMITTED:
                await self._register_close_submitted(directive, report)
            await self._register_close_update(directive, report)

    async def _register_close_submitted(
        self, directive: TradeDirective, report: ExecutionReport
    ) -> None:
        open_id = self._close_map.get(directive.directive_id)
        candidate = self._positions.get(open_id) if open_id else None
        if candidate is None:
            candidate = self._find_position_for_close(directive)
        if candidate is None:
            return

        order_id = None
        for note in report.notes:
            if note.startswith("order_id="):
                order_id = note.split("=", 1)[1]
                break

        candidate.last_close_order_id = order_id
        candidate.last_close_directive_id = directive.directive_id
        candidate.last_close_order_type = directive.order_type
        candidate.last_close_issued_at = directive.issued_at
        candidate.last_close_escalated = False

    async def _publish_event(
        self,
        event_type: PositionEventType,
        *,
        directive_id: str,
        symbol: str,
        direction: str,
        quantity: float | None = None,
        price: float | None = None,
        reason: str | None = None,
        status: str | None = None,
        origin_directive_id: str | None = None,
        notes: list[str] | None = None,
    ) -> None:
        event = PositionEvent(
            event=event_type,
            directive_id=directive_id,
            symbol=symbol,
            direction=direction,
            created_at=datetime.now(timezone.utc),
            quantity=quantity,
            price=price,
            reason=reason,
            status=status,
            origin_directive_id=origin_directive_id,
            notes=notes or [],
        )
        await self._bus.publish(streams.POSITION_EVENTS, event)

    async def _register_open_fill(
        self, directive: TradeDirective, report: ExecutionReport
    ) -> None:
        tracker = self._positions.get(directive.directive_id)
        fill_qty = report.quantity or 0.0
        quantity = max(fill_qty, directive.quantity or 0.0)
        now = datetime.now(timezone.utc)
        if tracker is None:
            tracker = TrackedPosition(
                directive_id=directive.directive_id,
                hypothesis_id=directive.hypothesis_id,
                symbol=directive.symbol,
                direction=directive.direction,
                quantity=quantity,
                entry_price=report.avg_price or directive.price,
                target_price=directive.take_profit_price,
                stop_price=directive.stop_loss_price,
                opened_at=report.reported_at or now,
                last_update=now,
            )
            self._positions[directive.directive_id] = tracker
            self._logger.info(
                "position_manager_track_open",
                directive_id=directive.directive_id,
                symbol=directive.symbol,
                quantity=quantity,
            )
            await self._publish_event(
                PositionEventType.OPEN_TRACKED,
                directive_id=directive.directive_id,
                symbol=directive.symbol,
                direction=directive.direction,
                quantity=tracker.quantity,
                price=tracker.entry_price,
                status=report.status.value,
            )
        else:
            tracker.quantity = max(tracker.quantity, quantity)
            tracker.entry_price = report.avg_price or tracker.entry_price
            tracker.last_update = now
            await self._publish_event(
                PositionEventType.OPEN_UPDATED,
                directive_id=directive.directive_id,
                symbol=directive.symbol,
                direction=directive.direction,
                quantity=tracker.quantity,
                price=tracker.entry_price,
                status=report.status.value,
            )
        tracker.close_requested = False
        tracker.last_price_event = None
        await self._notifier.broadcast(await self._store.build_dashboard_state())

    async def _register_close_update(
        self, directive: TradeDirective, report: ExecutionReport
    ) -> None:
        open_id = self._close_map.get(directive.directive_id)
        candidate = self._positions.get(open_id) if open_id else None
        if candidate is None:
            candidate = self._find_position_for_close(directive)
        if candidate is None:
            self._logger.debug(
                "position_manager_close_without_open",
                directive_id=directive.directive_id,
                symbol=directive.symbol,
            )
            return

        if report.status in {
            ExecutionStatus.FILLED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.FAILED,
            ExecutionStatus.REJECTED,
        }:
            if report.status is ExecutionStatus.FILLED:
                self._positions.pop(candidate.directive_id, None)
            else:
                candidate.close_requested = False
            self._logger.info(
                "position_manager_position_closed",
                directive_id=candidate.directive_id,
                close_directive=directive.directive_id,
                status=report.status.value,
            )
            if report.status is ExecutionStatus.FILLED:
                await self._store.remove_directive(candidate.directive_id)
            await self._store.remove_directive(directive.directive_id)
            await self._publish_event(
                PositionEventType.CLOSE_CONFIRMED,
                directive_id=directive.directive_id,
                symbol=directive.symbol,
                direction=directive.direction,
                quantity=report.quantity,
                price=report.avg_price,
                status=report.status.value,
                origin_directive_id=candidate.directive_id,
                notes=report.notes,
            )
            self._close_map.pop(directive.directive_id, None)
            await self._notifier.broadcast(await self._store.build_dashboard_state())
        elif report.status is ExecutionStatus.PARTIALLY_FILLED:
            candidate.quantity = max(0.0, candidate.quantity - (report.quantity or 0.0))
            candidate.last_update = datetime.now(timezone.utc)
            await self._publish_event(
                PositionEventType.CLOSE_PARTIAL,
                directive_id=directive.directive_id,
                symbol=directive.symbol,
                direction=directive.direction,
                quantity=report.quantity,
                price=report.avg_price,
                status=report.status.value,
                origin_directive_id=candidate.directive_id,
                notes=report.notes,
            )

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _find_position_for_close(
        self, directive: TradeDirective
    ) -> Optional[TrackedPosition]:
        for tracker in self._positions.values():
            if (
                tracker.symbol == directive.symbol
                and tracker.direction == directive.direction
            ):
                return tracker
        return None

    async def _evaluate_positions(self) -> None:
        if not self._positions:
            return

        try:
            config = await self._config_manager.get_config()
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("position_manager_config_unavailable", error=str(exc))
            return

        await self._enforce_limit_exit_timeouts(config)

        try:
            risk_budget = await self._store.get_risk_budget()
        except Exception as exc:  # noqa: BLE001
            self._logger.debug("position_manager_budget_unavailable", error=str(exc))
            risk_budget = {}

        portfolio_limit = (
            self._safe_float(risk_budget.get("portfolio_limit")) if risk_budget else 0.0
        )
        symbol_limits = (risk_budget or {}).get("symbol_limits") or {}
        base_portfolio_limit = self._safe_float(
            getattr(config, "max_portfolio_exposure_usdt", 0.0)
        )
        effective_portfolio_limit = (
            portfolio_limit if portfolio_limit > 0 else base_portfolio_limit
        )
        fallback_symbol_limit = 0.0
        if effective_portfolio_limit > 0:
            fallback_symbol_limit = effective_portfolio_limit * self._safe_float(
                getattr(config, "max_symbol_allocation_pct", 0.0)
            )
        elif base_portfolio_limit > 0:
            fallback_symbol_limit = base_portfolio_limit * self._safe_float(
                getattr(config, "max_symbol_allocation_pct", 0.0)
            )

        trackers = [
            tracker
            for tracker in self._positions.values()
            if not tracker.close_requested
        ]
        if not trackers:
            return

        observations: list[dict[str, Any]] = []
        total_exposure = 0.0
        now = datetime.now(timezone.utc)
        for tracker in trackers:
            reasons: list[str] = []
            price = None

            try:
                ticker = await self._client.get_symbol_ticker(tracker.symbol)
                price = float(ticker.last_price)
                tracker.last_price_event = None
            except Exception as exc:  # noqa: BLE001
                self._logger.debug(
                    "position_manager_price_fetch_failed",
                    symbol=tracker.symbol,
                    error=str(exc),
                )
                if (
                    tracker.last_price_event is None
                    or now - tracker.last_price_event >= timedelta(minutes=1)
                ):
                    await self._publish_event(
                        PositionEventType.PRICE_FETCH_FAILED,
                        directive_id=tracker.directive_id,
                        symbol=tracker.symbol,
                        direction=tracker.direction,
                        quantity=tracker.quantity,
                        notes=[str(exc)],
                    )
                    tracker.last_price_event = now

            symbol_key = tracker.symbol.upper()
            symbol_limit_raw = symbol_limits.get(symbol_key)
            symbol_limit = self._safe_float(symbol_limit_raw)
            effective_symbol_limit = (
                symbol_limit if symbol_limit > 0 else fallback_symbol_limit
            )

            reference_price = price
            if reference_price is None or reference_price <= 0:
                reference_price = self._safe_float(tracker.entry_price)
            notional = max(0.0, reference_price * self._safe_float(tracker.quantity))
            total_exposure += notional

            if price is not None:
                if tracker.direction == "long":
                    if tracker.target_price and price >= tracker.target_price:
                        reasons.append("target_hit")
                    elif tracker.stop_price and price <= tracker.stop_price:
                        reasons.append("stop_loss")
                else:  # short
                    if tracker.target_price and price <= tracker.target_price:
                        reasons.append("target_hit")
                    elif tracker.stop_price and price >= tracker.stop_price:
                        reasons.append("stop_loss")

            max_age = timedelta(
                minutes=float(config.position_manager_force_close_minutes)
            )
            if tracker.opened_at and now - tracker.opened_at >= max_age:
                reasons.append("timeout")

            if effective_symbol_limit > 0 and notional > effective_symbol_limit:
                reasons.append("symbol_limit")

            observations.append(
                {
                    "tracker": tracker,
                    "price": price,
                    "reasons": reasons,
                    "notional": notional,
                    "effective_symbol_limit": effective_symbol_limit,
                    "symbol_limit": symbol_limit,
                    "fallback_symbol_limit": fallback_symbol_limit,
                    "effective_portfolio_limit": effective_portfolio_limit,
                }
            )

        if effective_portfolio_limit > 0 and total_exposure > effective_portfolio_limit:
            excess = total_exposure - effective_portfolio_limit
            for obs in sorted(
                observations, key=lambda item: item["notional"], reverse=True
            ):
                if excess <= 0:
                    break
                notional = obs["notional"]
                if notional <= 0:
                    continue
                if "portfolio_limit" not in obs["reasons"]:
                    obs["reasons"].append("portfolio_limit")
                excess -= notional

        for obs in observations:
            tracker = obs["tracker"]
            if tracker.close_requested:
                continue
            reasons = obs["reasons"]
            if not reasons:
                continue
            await self._dispatch_close(
                tracker,
                obs["price"],
                reasons[0],
                config,
                notional=float(obs.get("notional") or 0.0),
                effective_symbol_limit=float(obs.get("effective_symbol_limit") or 0.0),
                effective_portfolio_limit=float(
                    obs.get("effective_portfolio_limit") or 0.0
                ),
            )

    async def _dispatch_close(
        self,
        tracker: TrackedPosition,
        market_price: Optional[float],
        reason: str,
        config,
        *,
        notional: float = 0.0,
        effective_symbol_limit: float = 0.0,
        effective_portfolio_limit: float = 0.0,
    ) -> None:
        tracker.close_requested = True
        directive_id = uuid4().hex

        use_market_exit = bool(
            getattr(config, "position_manager_use_market_exit", True)
        )
        order_type = "market"
        limit_price: Optional[float] = None
        if reason in {"stop_loss", "target_hit"} and not use_market_exit:
            order_type = "limit"
            if reason == "stop_loss":
                limit_price = tracker.stop_price
            else:
                limit_price = tracker.target_price
            if limit_price is None or limit_price <= 0:
                order_type = "market"
                limit_price = None
            else:
                # Ensure we don't place an obviously unfillable limit far away from the market.
                ref = market_price or tracker.entry_price
                if ref and ref > 0:
                    slip = max(
                        0.001,
                        float(getattr(config, "default_stop_loss_pct", 0.005)) * 2,
                    )
                    if tracker.direction == "long":
                        cap = ref * (1 - slip)
                        limit_price = min(limit_price, cap)
                    else:
                        cap = ref * (1 + slip)
                        limit_price = max(limit_price, cap)

        directive = TradeDirective(
            directive_id=directive_id,
            hypothesis_id=tracker.hypothesis_id,
            symbol=tracker.symbol,
            issued_at=datetime.now(timezone.utc),
            action=TradeAction.CLOSE,
            rationale=[f"Position manager: {reason}"],
            mode=self._orchestrator.mode,
            confidence=1.0,
            direction=tracker.direction,
            order_type=order_type,
            quantity=max(tracker.quantity, 0.0),
            price=limit_price if order_type == "limit" else market_price,
            time_in_force="GTC",
            leverage=1.0,
            reduce_only=True,
            notional_usdt=(market_price or tracker.entry_price or 0.0)
            * tracker.quantity,
            take_profit_price=None,
            stop_loss_price=None,
        )

        self._close_map[directive_id] = tracker.directive_id
        await self._store.upsert_directive(directive)
        decision = self._orchestrator.build_decision(
            directive,
            source="position_manager",
            meta={"origin_directive": tracker.directive_id, "reason": reason},
        )
        await self._bus.publish(streams.CTOAI_DIRECTIVES, directive)
        await self._bus.publish(streams.CTOAI_DECISIONS, decision)
        event_type = (
            PositionEventType.FORCE_CLOSE_TIMEOUT
            if reason == "timeout"
            else PositionEventType.CLOSE_REQUESTED
        )
        await self._publish_event(
            event_type,
            directive_id=directive_id,
            symbol=tracker.symbol,
            direction=tracker.direction,
            quantity=tracker.quantity,
            price=market_price,
            reason=reason,
            origin_directive_id=tracker.directive_id,
        )
        await self._notifier.broadcast(await self._store.build_dashboard_state())
        self._logger.info(
            "position_manager_close_emitted",
            close_directive=directive_id,
            origin_directive=tracker.directive_id,
            symbol=tracker.symbol,
            reason=reason,
            quantity=round(float(tracker.quantity or 0.0), 12),
            market_price=(
                round(float(market_price or 0.0), 8)
                if market_price is not None
                else None
            ),
            entry_price=(
                round(float(tracker.entry_price or 0.0), 8)
                if tracker.entry_price is not None
                else None
            ),
            notional=round(float(notional or 0.0), 8),
            effective_symbol_limit=round(float(effective_symbol_limit or 0.0), 8),
            effective_portfolio_limit=round(float(effective_portfolio_limit or 0.0), 8),
            max_portfolio_exposure_usdt=float(
                getattr(config, "max_portfolio_exposure_usdt", 0.0) or 0.0
            ),
            max_symbol_allocation_pct=float(
                getattr(config, "max_symbol_allocation_pct", 0.0) or 0.0
            ),
        )

    async def _enforce_limit_exit_timeouts(self, config) -> None:
        timeout_seconds = float(
            getattr(config, "position_manager_limit_exit_timeout_seconds", 0.0) or 0.0
        )
        if timeout_seconds <= 0:
            return

        now = datetime.now(timezone.utc)
        for tracker in list(self._positions.values()):
            if not tracker.close_requested:
                continue
            if tracker.last_close_escalated:
                continue
            if tracker.last_close_order_type != "limit":
                continue
            if tracker.last_close_reason not in {"stop_loss", "target_hit"}:
                continue
            if tracker.last_close_issued_at is None:
                continue
            if (now - tracker.last_close_issued_at).total_seconds() < timeout_seconds:
                continue
            if not tracker.last_close_order_id:
                continue

            try:
                await self._client.cancel_order(
                    tracker.symbol, tracker.last_close_order_id
                )
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "position_manager_limit_close_cancel_failed",
                    symbol=tracker.symbol,
                    order_id=tracker.last_close_order_id,
                    error=str(exc),
                )
                continue

            tracker.last_close_escalated = True
            tracker.close_requested = False
            await self._dispatch_close(tracker, None, "limit_exit_timeout", config)


async def run_position_manager(
    stop_event: asyncio.Event,
    bus: EventBus,
    orchestrator: CTOAIOrchestrator,
    store: GlobalAppState,
    notifier: BroadcastManager,
    config_manager: RuntimeConfigManager,
) -> None:
    manager = PositionManager(bus, orchestrator, store, notifier, config_manager)
    await manager.run(stop_event)
