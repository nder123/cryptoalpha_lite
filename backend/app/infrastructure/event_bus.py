"""Redis Streams backed event bus."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from json import dumps, loads
from typing import Any, AsyncIterator, Dict, Generic, Type, TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(
        f"Object of type {value.__class__.__name__} is not JSON serializable"
    )


@dataclass(slots=True)
class EventMessage(Generic[T]):
    """Envelope for events consumed from Redis Streams."""

    message_id: str
    stream: str
    payload: T


class EventBus:
    """Typed event bus built on Redis Streams."""

    def __init__(self, redis_client: redis.Redis[Any], *, maxlen: int | None = None):
        self._redis = redis_client
        self._group_created: Dict[str, bool] = {}
        self._maxlen = maxlen

    @classmethod
    async def create(cls) -> "EventBus":
        settings = get_settings()
        client = redis.from_url(
            settings.redis_dsn, encoding="utf-8", decode_responses=True
        )
        return cls(client, maxlen=settings.redis_stream_maxlen)

    async def publish(self, stream: str, event: Any, *, id: str | None = None) -> str:
        if isinstance(event, BaseModel):
            data = event.model_dump(mode="json")
        elif is_dataclass(event):
            data = asdict(event)
        else:
            raise TypeError(f"Unsupported event type: {event.__class__.__name__}")

        payload = dumps(
            {"type": event.__class__.__name__, "data": data}, default=_json_default
        )
        xadd_kwargs: dict[str, Any] = {"fields": {"payload": payload}}
        if self._maxlen is not None:
            xadd_kwargs["maxlen"] = self._maxlen
            xadd_kwargs["approximate"] = True
        if id is not None:
            xadd_kwargs["id"] = id
        message_id = await self._redis.xadd(stream, **xadd_kwargs)
        return message_id

    async def ensure_group(self, stream: str, group: str) -> None:
        if self._group_created.get(f"{stream}:{group}"):
            return
        try:
            await self._redis.xgroup_create(stream, group, id="$", mkstream=True)
        except redis.ResponseError as exc:  # group exists
            if "BUSYGROUP" not in str(exc):
                raise
        self._group_created[f"{stream}:{group}"] = True

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        await self._redis.xack(stream, group, message_id)

    async def listen(
        self,
        stream: str,
        group: str,
        event_type: Type[T],
        *,
        count: int = 10,
        block_ms: int = 5000,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[EventMessage[T]]:
        await self.ensure_group(stream, group)
        pending_cursor: str = "0-0"
        min_idle_ms = max(0, int(block_ms))
        while True:
            if stop_event and stop_event.is_set():
                return
            try:
                next_cursor, pending_messages, _ = await self._redis.xautoclaim(
                    stream,
                    group,
                    get_settings().app_name,
                    min_idle_ms,
                    pending_cursor,
                    count=count,
                )
            except Exception:  # noqa: BLE001
                pending_messages = []
                next_cursor = pending_cursor

            if pending_messages:
                pending_cursor = str(next_cursor)
                for message_id, fields in pending_messages:
                    payload = loads(fields["payload"])
                    data_payload = payload["data"]
                    if isinstance(event_type, type) and issubclass(
                        event_type, BaseModel
                    ):
                        data = event_type.model_validate(data_payload)
                    else:
                        data = event_type(**data_payload)  # type: ignore[arg-type]
                    yield EventMessage(
                        message_id=message_id, stream=stream, payload=data
                    )
                continue

            response = await self._redis.xreadgroup(
                group,
                get_settings().app_name,
                {stream: ">"},
                count=count,
                block=block_ms,
            )
            if not response:
                await asyncio.sleep(0)
                continue
            for _, messages in response:
                for message_id, fields in messages:
                    payload = loads(fields["payload"])
                    data_payload = payload["data"]
                    if isinstance(event_type, type) and issubclass(
                        event_type, BaseModel
                    ):
                        data = event_type.model_validate(data_payload)
                    else:
                        data = event_type(**data_payload)  # type: ignore[arg-type]
                    yield EventMessage(
                        message_id=message_id, stream=stream, payload=data
                    )

    def _decode_raw_message(
        self, stream: str, message_id: str, fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        payload_raw = fields.get("payload")
        if not payload_raw:
            return None
        try:
            payload = loads(payload_raw)
        except Exception:  # noqa: BLE001
            return None
        event_type = payload.get("type", "Unknown")
        data_payload = payload.get("data", {})
        timestamp: str | None = None
        try:
            millis_str, *_ = message_id.split("-", 1)
            millis = int(millis_str)
        except (ValueError, TypeError):
            timestamp = None
        else:
            timestamp = datetime.fromtimestamp(
                millis / 1000.0, tz=timezone.utc
            ).isoformat()
        return {
            "id": message_id,
            "stream": stream,
            "event_type": event_type,
            "timestamp": timestamp,
            "data": data_payload,
        }

    async def fetch_recent(
        self, stream: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return latest events from a Redis stream (newest first)."""
        if limit <= 0:
            return []
        messages = await self._redis.xrevrange(stream, max="+", min="-", count=limit)
        events: list[dict[str, Any]] = []
        for message_id, fields in messages:
            decoded = self._decode_raw_message(stream, message_id, fields)
            if decoded:
                events.append(decoded)
        return events

    async def fetch_after(
        self, stream: str, after_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return events newer than the provided ID (oldest first)."""
        if limit <= 0:
            return []
        start_id = f"({after_id}"
        messages = await self._redis.xrange(stream, min=start_id, max="+", count=limit)
        events: list[dict[str, Any]] = []
        for message_id, fields in messages:
            decoded = self._decode_raw_message(stream, message_id, fields)
            if decoded:
                events.append(decoded)
        return events

    async def close(self) -> None:
        await self._redis.aclose()


@asynccontextmanager
async def event_bus() -> AsyncIterator[EventBus]:
    bus = await EventBus.create()
    try:
        yield bus
    finally:
        await bus.close()
