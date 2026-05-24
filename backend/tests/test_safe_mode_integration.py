"""Integration: SAFE_MODE in runtime artifact → BybitExchangeAdapter.submit raises."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.exchange.bybit_adapter import BybitExchangeAdapter
from app.services.runtime_health_reader import (
    RuntimeHealthReader,
    set_default_reader_for_tests,
)
from app.services.trading_gate import TradingNotAllowed


def _write(path: Path, state: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "runtime_health.v1",
        "state": state,
        "since": "2026-05-24T13:00:00+03:00",
        "previous_state": "HEALTHY",
        "transition_id": "tid",
        "reasons": ["test"],
        "probes": {},
        "recovery_mode": False,
        "trading_enabled": state not in {"SAFE_MODE", "CRITICAL", "STALLED"},
        "runtime_mode": "PAPER",
        "operator_acknowledged": False,
        "next_evaluation_at": None,
        "evaluation_cadence_sec": 10,
    }))


class _FakeClient:
    """Stub that records calls and never touches the network."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def place_order(self, **kwargs):
        self.calls.append(kwargs)
        from app.exchange.bybit import OrderPlacementResult
        return OrderPlacementResult(order_id="x", status="ok", qty="1.0")


@pytest.fixture(autouse=True)
def _reset_default_reader():
    set_default_reader_for_tests(None)
    yield
    set_default_reader_for_tests(None)


def _install(state: str, tmp_path: Path) -> None:
    artifact = tmp_path / "runtime_health.json"
    _write(artifact, state)
    set_default_reader_for_tests(RuntimeHealthReader(path=artifact))


def _submit(adapter: BybitExchangeAdapter):
    return asyncio.run(
        adapter.submit(
            symbol="BTCUSDT",
            side="Buy",
            order_type="Market",
            qty="1.0",
        )
    )


def test_submit_blocked_in_safe_mode(tmp_path):
    _install("SAFE_MODE", tmp_path)
    client = _FakeClient()
    adapter = BybitExchangeAdapter(client=client)  # type: ignore[arg-type]
    with pytest.raises(TradingNotAllowed):
        _submit(adapter)
    assert client.calls == []  # never reached the exchange


def test_submit_blocked_in_critical(tmp_path):
    _install("CRITICAL", tmp_path)
    client = _FakeClient()
    adapter = BybitExchangeAdapter(client=client)  # type: ignore[arg-type]
    with pytest.raises(TradingNotAllowed):
        _submit(adapter)
    assert client.calls == []


def test_submit_blocked_in_stalled(tmp_path):
    _install("STALLED", tmp_path)
    client = _FakeClient()
    adapter = BybitExchangeAdapter(client=client)  # type: ignore[arg-type]
    with pytest.raises(TradingNotAllowed):
        _submit(adapter)
    assert client.calls == []


def test_submit_blocked_when_artifact_missing(tmp_path):
    set_default_reader_for_tests(RuntimeHealthReader(path=tmp_path / "absent.json"))
    client = _FakeClient()
    adapter = BybitExchangeAdapter(client=client)  # type: ignore[arg-type]
    with pytest.raises(TradingNotAllowed):
        _submit(adapter)
    assert client.calls == []


def test_submit_proceeds_in_healthy(tmp_path):
    _install("HEALTHY", tmp_path)
    client = _FakeClient()
    adapter = BybitExchangeAdapter(client=client)  # type: ignore[arg-type]
    result = _submit(adapter)
    assert len(client.calls) == 1
    assert result.exchange_order_id == "x"


def test_submit_proceeds_in_degraded(tmp_path):
    _install("DEGRADED", tmp_path)
    client = _FakeClient()
    adapter = BybitExchangeAdapter(client=client)  # type: ignore[arg-type]
    result = _submit(adapter)
    assert len(client.calls) == 1
    assert result.exchange_order_id == "x"


def test_submit_evidence_written_on_denial(tmp_path, monkeypatch):
    """Denial path must produce structured evidence (logged or persisted)."""
    _install("SAFE_MODE", tmp_path)
    client = _FakeClient()
    adapter = BybitExchangeAdapter(client=client)  # type: ignore[arg-type]
    try:
        _submit(adapter)
    except TradingNotAllowed as e:
        ev = e.as_evidence()
        assert ev["event"] == "execution_denied"
        assert ev["state"] == "SAFE_MODE"
        assert ev["component"] == "bybit_adapter"
        assert ev["attempted_action"].startswith("submit_")
    else:
        pytest.fail("expected TradingNotAllowed")
