"""Monitor Bybit orders to emit filled execution reports."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Optional

from app.core.logging import get_logger
from app.domain import streams
from app.domain.events import ExecutionReport, ExecutionStatus
from app.exchange.bybit import BybitClient, OrderStatusInfo
from app.infrastructure.event_bus import EventBus

_PENDING_MAX = 512


@dataclass(slots=True)
class _PendingOrder:
    directive_id: str
    symbol: str
    order_id: str
    last_status: str
    last_qty: Optional[float]
    last_avg_price: Optional[float]
    last_fee: Optional[float]
    last_update: datetime


class ExecutionFillMonitor:
    """Background task that polls Bybit for order fills and emits execution updates."""

    def __init__(self, bus: EventBus, poll_interval: float = 3.0) -> None:
        self._logger = get_logger(__name__)
        self._bus = bus
        self._client = BybitClient()
        self._poll_interval = poll_interval
        self._pending: Dict[str, _PendingOrder] = {}
        self._order: Deque[str] = deque(maxlen=_PENDING_MAX)

    async def run(self, stop_event: asyncio.Event) -> None:
        consumer = asyncio.create_task(self._consume_reports(stop_event))
        poller = asyncio.create_task(self._poll_orders(stop_event))
        try:
            await asyncio.gather(consumer, poller)
        finally:
            consumer.cancel()
            poller.cancel()
            await self._client.close()

    async def _consume_reports(self, stop_event: asyncio.Event) -> None:
        group = "fill-monitor"
        async for message in self._bus.listen(
            streams.EXECUTION_REPORTS,
            group=group,
            event_type=ExecutionReport,
            stop_event=stop_event,
        ):
            report = message.payload
            try:
                await self._handle_report(report)
            finally:
                await self._bus.ack(message.stream, group, message.message_id)
            if stop_event.is_set():
                break

    async def _handle_report(self, report: ExecutionReport) -> None:
        if report.status not in {
            ExecutionStatus.SUBMITTED,
            ExecutionStatus.PARTIALLY_FILLED,
        }:
            return

        order_id = self._extract_order_id(report)
        if not order_id:
            self._logger.debug(
                "fill_monitor_missing_order_id", directive_id=report.directive_id
            )
            return

        pending_key = report.directive_id
        existing = self._pending.get(pending_key)
        if existing is None:
            if self._order.maxlen and len(self._order) == self._order.maxlen:
                oldest = self._order.popleft()
                self._pending.pop(oldest, None)
            pending = _PendingOrder(
                directive_id=report.directive_id,
                symbol=report.symbol,
                order_id=order_id,
                last_status=report.status.value,
                last_qty=None,
                last_avg_price=None,
                last_fee=None,
                last_update=datetime.now(tz=timezone.utc),
            )
            self._pending[pending_key] = pending
            self._order.append(pending_key)
        else:
            existing.order_id = order_id
            existing.last_status = report.status.value
            existing.last_update = datetime.now(tz=timezone.utc)

    async def _poll_orders(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._drain_pending()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                continue

    async def _drain_pending(self) -> None:
        if not self._pending:
            return

        to_remove: list[str] = []
        for directive_id, pending in list(self._pending.items()):
            info = await self._fetch_status(pending)
            if info is None:
                continue

            normalized = (info.status or "").lower()
            status_changed = normalized != (pending.last_status or "").lower()
            qty_changed = (
                info.cum_exec_qty is not None and info.cum_exec_qty != pending.last_qty
            )
            price_changed = (
                info.avg_price is not None and info.avg_price != pending.last_avg_price
            )
            fee_changed = (
                info.cum_exec_fee is not None and info.cum_exec_fee != pending.last_fee
            )

            if not (status_changed or qty_changed or price_changed or fee_changed):
                continue

            if normalized in {"filled"}:
                await self._publish_update(
                    pending, info, ExecutionStatus.FILLED, "filled"
                )
                to_remove.append(directive_id)
            elif normalized in {"partiallyfilled"}:
                await self._publish_update(
                    pending, info, ExecutionStatus.PARTIALLY_FILLED, "partial"
                )
                pending.last_status = normalized
                pending.last_qty = info.cum_exec_qty
                pending.last_avg_price = info.avg_price
                pending.last_fee = info.cum_exec_fee
                pending.last_update = datetime.now(tz=timezone.utc)
            elif normalized in {"cancelled", "canceled"}:
                await self._publish_update(
                    pending, info, ExecutionStatus.CANCELLED, "cancelled"
                )
                to_remove.append(directive_id)
            elif normalized in {"rejected"}:
                await self._publish_update(
                    pending, info, ExecutionStatus.REJECTED, "rejected"
                )
                to_remove.append(directive_id)
            elif normalized in {"failed", "deactivated"}:
                await self._publish_update(
                    pending, info, ExecutionStatus.FAILED, "failed"
                )
                to_remove.append(directive_id)
            else:
                pending.last_status = normalized
                pending.last_qty = (
                    info.cum_exec_qty
                    if info.cum_exec_qty is not None
                    else pending.last_qty
                )
                pending.last_avg_price = (
                    info.avg_price
                    if info.avg_price is not None
                    else pending.last_avg_price
                )
                pending.last_fee = (
                    info.cum_exec_fee
                    if info.cum_exec_fee is not None
                    else pending.last_fee
                )
                pending.last_update = datetime.now(tz=timezone.utc)

        for directive_id in to_remove:
            self._pending.pop(directive_id, None)
            try:
                self._order.remove(directive_id)
            except ValueError:
                pass

    async def _fetch_status(self, pending: _PendingOrder) -> Optional[OrderStatusInfo]:
        try:
            info = await self._client.get_order_status(pending.symbol, pending.order_id)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "fill_monitor_status_failed",
                directive_id=pending.directive_id,
                order_id=pending.order_id,
                error=str(exc),
            )
            return None
        if info is None:
            self._logger.debug(
                "fill_monitor_status_missing",
                directive_id=pending.directive_id,
                order_id=pending.order_id,
            )
        return info

    async def _publish_update(
        self,
        pending: _PendingOrder,
        info: OrderStatusInfo,
        status: ExecutionStatus,
        tag: str,
    ) -> None:
        reported_at = (
            info.updated_at.astimezone(timezone.utc)
            if info.updated_at
            else datetime.now(timezone.utc)
        )
        quantity = (
            info.cum_exec_qty
            if info.cum_exec_qty is not None
            else pending.last_qty or 0.0
        )
        avg_price = (
            info.avg_price if info.avg_price is not None else pending.last_avg_price
        )
        fees = info.cum_exec_fee if info.cum_exec_fee is not None else pending.last_fee
        if (
            status in {ExecutionStatus.FILLED, ExecutionStatus.PARTIALLY_FILLED}
            and fees is None
        ):
            fees = await self._fallback_fetch_order_fee(
                pending.symbol, pending.order_id
            )

        report = ExecutionReport(
            directive_id=pending.directive_id,
            symbol=pending.symbol,
            status=status,
            quantity=quantity or 0.0,
            avg_price=avg_price,
            fees_paid=fees,
            reported_at=reported_at,
            notes=[
                f"order_id={pending.order_id}",
                f"status={info.status}",
                f"fill_monitor={tag}",
            ],
        )
        await self._bus.publish(streams.EXECUTION_REPORTS, report)

    async def _fallback_fetch_order_fee(
        self, symbol: str, order_id: str
    ) -> Optional[float]:
        now = datetime.now(timezone.utc)
        try:
            executions, _ = await self._client.fetch_executions(
                symbol=symbol,
                start_time=now - timedelta(hours=2),
                end_time=now,
                limit=200,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.debug(
                "fill_monitor_fee_fallback_failed",
                symbol=symbol,
                order_id=order_id,
                error=str(exc),
            )
            return None

        fee_sum = 0.0
        matched = False
        for entry in executions or []:
            if str(entry.get("order_id") or "") != order_id:
                continue
            matched = True
            try:
                fee_sum += float(entry.get("fee") or 0.0)
            except (TypeError, ValueError):
                continue

        if not matched:
            return None
        return fee_sum

    @staticmethod
    def _extract_order_id(report: ExecutionReport) -> Optional[str]:
        for note in report.notes:
            if note.startswith("order_id="):
                return note.split("=", 1)[1]
        return None


async def run_execution_fill_monitor(
    stop_event: asyncio.Event, bus: EventBus, poll_interval: float = 3.0
) -> None:
    monitor = ExecutionFillMonitor(bus, poll_interval=poll_interval)
    await monitor.run(stop_event)
