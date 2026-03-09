"""Audit logger service that persists key events."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Type

from app.core.logging import get_logger
from app.domain import streams
from app.domain.events import (
    ExecutionReport,
    MarketSnapshot,
    RejectedHypothesis,
    RiskAssessment,
    TradeDirective,
    TradeHypothesis,
)
from app.infrastructure.event_bus import EventBus
from app.repositories.event_logs import EventLogRepository

EventType = Type


class AuditLogger:
    """Fan-out listener that stores domain events for audit trail."""

    def __init__(self, bus: EventBus, repository: EventLogRepository) -> None:
        self._bus = bus
        self._repository = repository
        self._logger = get_logger(__name__)
        self._tasks: list[asyncio.Task[None]] = []

    async def run(self, stop_event: asyncio.Event) -> None:
        mapping: Dict[str, EventType] = {
            streams.MARKET_SNAPSHOTS: MarketSnapshot,
            streams.RESEARCH_HYPOTHESES: TradeHypothesis,
            streams.RESEARCH_REJECTIONS: RejectedHypothesis,
            streams.RISK_ASSESSMENTS: RiskAssessment,
            streams.CTOAI_DIRECTIVES: TradeDirective,
            streams.EXECUTION_REPORTS: ExecutionReport,
        }

        for stream, event_type in mapping.items():
            task = asyncio.create_task(self._consume(stream, event_type, stop_event))
            self._tasks.append(task)

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            for task in self._tasks:
                task.cancel()
            raise

    async def _consume(
        self, stream: str, event_type: EventType, stop_event: asyncio.Event
    ) -> None:
        group = "audit"
        async for message in self._bus.listen(
            stream,
            group=group,
            event_type=event_type,
            stop_event=stop_event,
        ):
            try:
                payload = message.payload
                payload_dict = self._normalize_payload(payload)
                await self._repository.record(
                    stream, payload.__class__.__name__, payload_dict
                )
            except Exception as exc:  # noqa: BLE001
                self._logger.error("audit_log_failed", stream=stream, error=str(exc))
            finally:
                await self._bus.ack(stream, group, message.message_id)
            if stop_event.is_set():
                break

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(mode="json")  # type: ignore[return-value]
        if isinstance(payload, dict):
            return payload
        raise TypeError(f"Unsupported payload type: {type(payload)!r}")


async def run_audit_logger(
    stop_event: asyncio.Event, bus: EventBus, repository: EventLogRepository
) -> None:
    logger = AuditLogger(bus, repository)
    await logger.run(stop_event)
