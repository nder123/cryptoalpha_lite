"""Repository for persisting event logs into PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select

from app.infrastructure.database import db_session
from app.repositories.models import EventLog


class EventLogRepository:
    """Provides methods to persist domain events for audit purposes."""

    async def record(self, stream: str, event_type: str, payload: dict[str, Any]) -> None:
        async with db_session() as session:
            stmt = (
                insert(EventLog)
                .values(
                    stream=stream,
                    event_type=event_type,
                    payload=payload,
                    created_at=datetime.now(timezone.utc),
                )
                .execution_options(populate_existing=False)
            )
            await session.execute(stmt)

    async def fetch_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        async with db_session() as session:
            stmt = (
                select(EventLog)
                .order_by(EventLog.id.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "id": row.id,
                    "stream": row.stream,
                    "event_type": row.event_type,
                    "payload": row.payload,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
