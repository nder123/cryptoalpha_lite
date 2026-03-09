"""Service to record trade statistics from directives and execution reports."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Deque, Dict, Optional

from app.core.logging import get_logger
from app.domain import streams
from app.domain.events import ExecutionReport, ExecutionStatus, TradeAction, TradeDirective
from app.infrastructure.event_bus import EventBus
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState
from app.repositories.trade_stats import (
    TradeCloseDTO,
    TradeFillDTO,
    TradeSessionDTO,
    TradeStatsRepository,
)

_DECIMAL_ZERO = Decimal("0")


def _to_decimal(value: Optional[float | int]) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value))


@dataclass(slots=True)
class _CachedDirective:
    directive: TradeDirective
    stored_at: datetime


class TradeStatsRecorder:
    """Background service storing executed trades for analytics."""

    def __init__(
        self,
        bus: EventBus,
        repository: TradeStatsRepository,
        store: GlobalAppState | None = None,
        notifier: BroadcastManager | None = None,
        cache_size: int = 4096,
    ) -> None:
        self._bus = bus
        self._repo = repository
        self._logger = get_logger(__name__)
        self._cache: Dict[str, _CachedDirective] = {}
        self._order = deque(maxlen=cache_size)  # type: Deque[str]
        self._store = store
        self._notifier = notifier

    async def run(self, stop_event: asyncio.Event) -> None:
        tasks = [
            asyncio.create_task(self._consume_directives(stop_event)),
            asyncio.create_task(self._consume_execution_reports(stop_event)),
        ]
        try:
            await self._refresh_overview()
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            raise

    async def _consume_directives(self, stop_event: asyncio.Event) -> None:
        group = "trade-stats-directives"
        async for message in self._bus.listen(
            streams.CTOAI_DIRECTIVES,
            group=group,
            event_type=TradeDirective,
            stop_event=stop_event,
        ):
            directive = message.payload
            self._remember_directive(directive)
            await self._bus.ack(message.stream, group, message.message_id)
            if stop_event.is_set():
                break

    async def _consume_execution_reports(self, stop_event: asyncio.Event) -> None:
        group = "trade-stats-execution"
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
                self._logger.error(
                    "trade_stats_execution_failed",
                    directive_id=report.directive_id,
                    error=str(exc),
                )
            finally:
                await self._bus.ack(message.stream, group, message.message_id)
            if stop_event.is_set():
                break

    def _remember_directive(self, directive: TradeDirective) -> None:
        if self._order.maxlen and len(self._order) == self._order.maxlen:
            expired_id = self._order.popleft()
            self._cache.pop(expired_id, None)
        self._order.append(directive.directive_id)
        self._cache[directive.directive_id] = _CachedDirective(
            directive=directive,
            stored_at=datetime.now(timezone.utc),
        )

    async def _handle_execution(self, report: ExecutionReport) -> None:
        cached = self._cache.get(report.directive_id)
        directive = cached.directive if cached is not None else None
        if directive is None and self._store is not None:
            directive = await self._store.get_directive(report.directive_id)
            if directive is not None:
                self._remember_directive(directive)
        if directive is None:
            self._logger.warning("trade_stats_missing_directive", directive_id=report.directive_id)
            return
        if directive.action not in {TradeAction.OPEN, TradeAction.CLOSE}:
            self._logger.debug(
                "trade_stats_ignoring_non_trade_action",
                directive_id=directive.directive_id,
                action=directive.action,
            )
            return

        if directive.action is TradeAction.OPEN:
            await self._handle_open_execution(directive, report)
        elif directive.action is TradeAction.CLOSE:
            await self._handle_close_execution(directive, report)

    async def _handle_open_execution(self, directive: TradeDirective, report: ExecutionReport) -> None:
        if report.status not in {ExecutionStatus.FILLED, ExecutionStatus.PARTIALLY_FILLED}:
            return

        entry_price = _to_decimal(report.avg_price)
        entry_qty = _to_decimal(report.quantity)
        session_id = directive.directive_id
        session = TradeSessionDTO(
            session_id=session_id,
            symbol=directive.symbol,
            direction=directive.direction,
            mode=directive.mode.value,
            opened_at=report.reported_at,
            entry_directive_id=directive.directive_id,
            entry_price=entry_price,
            entry_qty=entry_qty,
            target_price=_to_decimal(directive.take_profit_price),
            stop_price=_to_decimal(directive.stop_loss_price),
            comment=", ".join(directive.rationale) if directive.rationale else None,
        )
        await self._repo.create_session(session)
        if directive.hypothesis_id:
            await self._repo.create_hypothesis_session(
                hypothesis_id=directive.hypothesis_id,
                session_id=session_id,
                symbol=directive.symbol,
                direction=directive.direction,
                opened_at=report.reported_at,
            )
        await self._refresh_overview()

        fill = TradeFillDTO(
            session_id=session_id,
            directive_id=directive.directive_id,
            order_id=report.notes[0] if report.notes else None,
            side=self._infer_side(directive, is_open=True),
            price=entry_price,
            quantity=entry_qty,
            fees=_to_decimal(report.fees_paid),
            reported_at=report.reported_at,
        )
        await self._repo.add_fill(fill)

    async def _handle_close_execution(self, directive: TradeDirective, report: ExecutionReport) -> None:
        if report.status not in {ExecutionStatus.FILLED, ExecutionStatus.PARTIALLY_FILLED}:
            return

        session = await self._repo.get_open_session(directive.symbol, directive.direction)
        if session is None:
            self._logger.warning("trade_stats_no_open_session", directive_id=directive.directive_id, symbol=directive.symbol)
            return

        exit_price = _to_decimal(report.avg_price)
        exit_qty = _to_decimal(report.quantity)
        entry_price = session.entry_price or _DECIMAL_ZERO
        entry_qty = session.entry_qty or exit_qty or _DECIMAL_ZERO

        pnl_usdt: Optional[Decimal] = None
        pnl_pct: Optional[Decimal] = None
        if exit_price is not None and entry_price is not None and entry_qty is not None:
            signed_qty = entry_qty if directive.direction == "long" else -entry_qty
            pnl_usdt = (exit_price - entry_price) * signed_qty
            denominator = entry_price * entry_qty
            if denominator != _DECIMAL_ZERO:
                pnl_pct = pnl_usdt / denominator

        duration_seconds: Optional[int] = None
        if session.opened_at and report.reported_at:
            duration_seconds = int((report.reported_at - session.opened_at).total_seconds())

        rationale_text = " ".join(directive.rationale or []).lower()
        tp_hit = self._check_level_hit(session.target_price, exit_price)
        sl_hit = self._check_level_hit(session.stop_price, exit_price)
        if "target_hit" in rationale_text or "take_profit" in rationale_text:
            tp_hit = True
        if "stop_loss" in rationale_text or "stoploss" in rationale_text:
            sl_hit = True

        rr_ratio = None
        if session.target_price and session.stop_price and entry_price and session.stop_price != entry_price:
            reward = abs(session.target_price - entry_price)
            risk = abs(entry_price - session.stop_price)
            if risk != _DECIMAL_ZERO:
                rr_ratio = reward / risk

        close_dto = TradeCloseDTO(
            session_id=session.session_id,
            closed_at=report.reported_at,
            exit_directive_id=directive.directive_id,
            exit_price=exit_price,
            exit_qty=exit_qty,
            pnl_usdt=pnl_usdt,
            pnl_pct=pnl_pct,
            tp_hit=tp_hit,
            sl_hit=sl_hit,
            duration_seconds=duration_seconds,
            risk_reward_ratio=rr_ratio,
            comment=", ".join(directive.rationale) if directive.rationale else session.comment,
        )
        await self._repo.close_session(close_dto)
        await self._repo.update_hypothesis_session_on_close(
            session_id=session.session_id,
            closed_at=report.reported_at,
            pnl_usdt=pnl_usdt,
            pnl_pct=pnl_pct,
        )

        fill = TradeFillDTO(
            session_id=session.session_id,
            directive_id=directive.directive_id,
            order_id=report.notes[0] if report.notes else None,
            side=self._infer_side(directive, is_open=False),
            price=exit_price,
            quantity=exit_qty,
            fees=_to_decimal(report.fees_paid),
            reported_at=report.reported_at,
        )
        await self._repo.add_fill(fill)
        await self._refresh_overview()

    @staticmethod
    def _infer_side(directive: TradeDirective, *, is_open: bool) -> str:
        if directive.direction == "long":
            return "Buy" if is_open else "Sell"
        return "Sell" if is_open else "Buy"

    @staticmethod
    def _check_level_hit(level: Optional[Decimal], price: Optional[Decimal], tolerance: Decimal = Decimal("0.001")) -> bool:
        if level is None or price is None:
            return False
        if level == _DECIMAL_ZERO:
            return False
        return abs(price - level) <= abs(level) * tolerance

    async def _refresh_overview(self) -> None:
        try:
            overview = await self._repo.dashboard_overview()
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("trade_stats_overview_failed", error=str(exc))
            return
        if self._store is None:
            return
        await self._store.set_trade_stats_overview(overview)
        if self._notifier is not None:
            await self._notifier.broadcast(await self._store.build_dashboard_state())


async def run_trade_stats_recorder(
    stop_event: asyncio.Event,
    bus: EventBus,
    repository: TradeStatsRepository,
    store: GlobalAppState,
    notifier: BroadcastManager,
) -> None:
    recorder = TradeStatsRecorder(bus, repository, store, notifier)
    await recorder.run(stop_event)
