from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = str(BACKEND_ROOT)
if BACKEND_PATH not in sys.path:  # pragma: no cover
    sys.path.insert(0, BACKEND_PATH)

from app.services import notification_dispatcher as nd


class _StubRedis:
    def __init__(self) -> None:
        self.backlog = 0
        self.last_run_values: list[str] = []

    async def zcard(self, key: str) -> int:
        assert key == nd.AUTO_RESEARCH_BACKLOG_KEY
        return self.backlog

    async def hvals(self, key: str) -> list[str]:
        assert key == nd.AUTO_RESEARCH_LAST_RUN_HASH
        return list(self.last_run_values)

    async def aclose(self) -> None:  # pragma: no cover - noop for tests
        return None


class _StubHTTPClient:
    async def post(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - notifications bypass network
        class _Response:
            @staticmethod
            def raise_for_status() -> None:
                return None

        return _Response()

    async def aclose(self) -> None:  # pragma: no cover - noop for tests
        return None


class _CapturingHTTPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def post(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))

        class _Response:
            @staticmethod
            def raise_for_status() -> None:
                return None

        return _Response()

    async def aclose(self) -> None:  # pragma: no cover - noop for tests
        return None


class _DummyConfigManager:
    async def get_config(self) -> SimpleNamespace:  # pragma: no cover - not used in tests here
        return SimpleNamespace()


class _StubLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def info(self, *args: Any, **kwargs: Any) -> None:
        self.records.append(("info", args, kwargs))

    def error(self, *args: Any, **kwargs: Any) -> None:
        self.records.append(("error", args, kwargs))


@pytest.mark.asyncio
async def test_auto_research_backlog_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_redis = _StubRedis()
    stub_redis.backlog = 80
    now = datetime.now(timezone.utc)
    stub_redis.last_run_values = [now.isoformat()]

    monkeypatch.setattr(nd.redis, "from_url", lambda *args, **kwargs: stub_redis)
    monkeypatch.setattr(nd.httpx, "AsyncClient", lambda timeout=10.0: _StubHTTPClient())

    dispatcher = nd.NotificationDispatcher(_DummyConfigManager())
    dispatcher._auto_research_enabled_last = True
    events: list[tuple[str, str]] = []

    async def _capture(event: str, message: str) -> None:
        events.append((event, message))

    dispatcher._send = _capture  # type: ignore[assignment]
    dispatcher._redis = stub_redis  # ensure our stub is used directly

    config = SimpleNamespace(auto_research_enabled=True, auto_research_batch_size=5, auto_research_interval_minutes=5)

    await dispatcher._handle_auto_research_alert(config)

    assert events and events[0][0] == "auto_research_backlog_high"
    assert "80" in events[0][1]


@pytest.mark.asyncio
async def test_auto_research_stale_and_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_redis = _StubRedis()
    stale_age = timedelta(minutes=5)
    stale_timestamp = datetime.now(timezone.utc) - stale_age
    stub_redis.backlog = 10
    stub_redis.last_run_values = [stale_timestamp.isoformat()]

    monkeypatch.setattr(nd.redis, "from_url", lambda *args, **kwargs: stub_redis)
    monkeypatch.setattr(nd.httpx, "AsyncClient", lambda timeout=10.0: _StubHTTPClient())

    dispatcher = nd.NotificationDispatcher(_DummyConfigManager())
    dispatcher._auto_research_enabled_last = True
    events: list[tuple[str, str]] = []

    async def _capture(event: str, message: str) -> None:
        events.append((event, message))

    dispatcher._send = _capture  # type: ignore[assignment]
    dispatcher._redis = stub_redis

    config = SimpleNamespace(auto_research_enabled=True, auto_research_batch_size=5, auto_research_interval_minutes=1)

    await dispatcher._handle_auto_research_alert(config)

    assert any(event == "auto_research_stale" for event, _ in events)

    # simulate recovery with a recent run
    stub_redis.last_run_values = [datetime.now(timezone.utc).isoformat()]

    await dispatcher._handle_auto_research_alert(config)

    assert any(event == "auto_research_recovered" for event, _ in events)


@pytest.mark.asyncio
async def test_send_dispatches_webhook_and_telegram(monkeypatch: pytest.MonkeyPatch) -> None:
    capturing_http = _CapturingHTTPClient()

    monkeypatch.setattr(nd.redis, "from_url", lambda *args, **kwargs: _StubRedis())
    monkeypatch.setattr(nd.httpx, "AsyncClient", lambda timeout=10.0: capturing_http)
    monkeypatch.setattr(nd, "LOGGER", _StubLogger())

    dispatcher = nd.NotificationDispatcher(_DummyConfigManager())
    dispatcher._http = capturing_http
    dispatcher._webhook_url = "https://hooks.example.com/notify"
    dispatcher._telegram_token = "test-token"
    dispatcher._telegram_chat_id = "12345"

    await dispatcher._send("test_event", "Привет")

    assert len(capturing_http.calls) == 2
    webhook_call, telegram_call = capturing_http.calls

    webhook_args, webhook_kwargs = webhook_call
    assert webhook_args[0] == "https://hooks.example.com/notify"
    assert webhook_kwargs["json"]["event"] == "test_event"
    assert webhook_kwargs["json"]["message"] == "Привет"

    telegram_args, telegram_kwargs = telegram_call
    assert telegram_args[0] == "https://api.telegram.org/bottest-token/sendMessage"
    assert telegram_kwargs["json"] == {"chat_id": "12345", "text": "Привет"}
