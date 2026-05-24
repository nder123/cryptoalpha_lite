"""Tests for S1-05 SAFE_MODE enforcement: reader, gate, policy projection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_health_reader import (
    RuntimeHealthReader,
    RuntimeHealthSnapshot,
    set_default_reader_for_tests,
)
from app.services.trading_gate import (
    ALLOWED_STATES,
    DENIED_STATES,
    RESTRICTED_STATES,
    GateDecision,
    TradingNotAllowed,
    assert_trading_allowed,
    derive_policy,
    is_trading_allowed,
)


def _write_artifact(path: Path, *, state: str, **extra) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "runtime_health.v1",
        "state": state,
        "since": "2026-05-24T13:00:00+03:00",
        "previous_state": "HEALTHY",
        "transition_id": "tid-1",
        "reasons": ["test"],
        "probes": {"P1": "pass", "P10": "pass"},
        "recovery_mode": False,
        "trading_enabled": state not in {"SAFE_MODE", "CRITICAL"},
        "runtime_mode": "PAPER",
        "operator_acknowledged": False,
        "next_evaluation_at": None,
        "evaluation_cadence_sec": 10,
    }
    payload.update(extra)
    path.write_text(json.dumps(payload))


@pytest.fixture
def reader_factory(tmp_path):
    def _make(state: str, **extra) -> RuntimeHealthReader:
        artifact = tmp_path / "runtime_health.json"
        _write_artifact(artifact, state=state, **extra)
        return RuntimeHealthReader(path=artifact)
    return _make


@pytest.fixture(autouse=True)
def _reset_default_reader():
    set_default_reader_for_tests(None)
    yield
    set_default_reader_for_tests(None)


# ── Reader ──────────────────────────────────────────────────────────────


def test_reader_returns_unknown_when_file_missing(tmp_path):
    r = RuntimeHealthReader(path=tmp_path / "absent.json")
    snap = r.read()
    assert snap.state == "UNKNOWN"
    assert snap.stale is True
    assert snap.stale_reason == "file_missing"


def test_reader_parses_healthy(reader_factory):
    snap = reader_factory("HEALTHY").read()
    assert snap.state == "HEALTHY"
    assert snap.stale is False
    assert snap.safe_mode_active is False


def test_reader_safe_mode_active_when_state_safe_mode(reader_factory):
    snap = reader_factory("SAFE_MODE").read()
    assert snap.safe_mode_active is True


def test_reader_coherence_break_count_from_p10(reader_factory):
    snap = reader_factory("CRITICAL", probes={"P10": "fail"}).read()
    assert snap.coherence_break_count == 1


def test_reader_falls_back_to_last_good_when_file_disappears(tmp_path):
    artifact = tmp_path / "runtime_health.json"
    _write_artifact(artifact, state="HEALTHY")
    r = RuntimeHealthReader(path=artifact)
    first = r.read()
    assert first.state == "HEALTHY"
    artifact.unlink()
    second = r.read()
    assert second.state == "HEALTHY"  # last-good
    assert second.stale is True
    assert second.stale_reason == "file_missing"


def test_reader_unparsable_returns_unknown_when_no_last_good(tmp_path):
    artifact = tmp_path / "runtime_health.json"
    artifact.write_text("not json {")
    r = RuntimeHealthReader(path=artifact)
    snap = r.read()
    assert snap.state == "UNKNOWN"
    assert snap.stale_reason == "parse_error"


# ── Gate decision matrix ────────────────────────────────────────────────


@pytest.mark.parametrize("state", sorted(ALLOWED_STATES))
def test_gate_allows_in_healthy_and_degraded(reader_factory, state):
    decision = is_trading_allowed(reader=reader_factory(state))
    assert decision.allowed is True
    assert decision.state == state


@pytest.mark.parametrize("state", sorted(DENIED_STATES - {"UNKNOWN"}))
def test_gate_denies_in_denied_states(reader_factory, state):
    decision = is_trading_allowed(reader=reader_factory(state))
    assert decision.allowed is False
    assert decision.state == state


def test_gate_denies_unknown_state(tmp_path):
    r = RuntimeHealthReader(path=tmp_path / "absent.json")
    decision = is_trading_allowed(reader=r)
    assert decision.allowed is False
    assert decision.state == "UNKNOWN"


@pytest.mark.parametrize("state", sorted(RESTRICTED_STATES))
def test_gate_restricted_state_denied_by_default(reader_factory, state):
    decision = is_trading_allowed(reader=reader_factory(state))
    assert decision.allowed is False
    assert decision.reason == "state_restricted"


@pytest.mark.parametrize("state", sorted(RESTRICTED_STATES))
def test_gate_restricted_state_allowed_with_explicit_flag(reader_factory, state):
    decision = is_trading_allowed(reader=reader_factory(state), allow_restricted=True)
    assert decision.allowed is True


# ── assert_trading_allowed: raise + evidence ────────────────────────────


def test_assert_trading_allowed_raises_in_safe_mode(reader_factory, monkeypatch):
    set_default_reader_for_tests(reader_factory("SAFE_MODE"))
    with pytest.raises(TradingNotAllowed) as exc:
        assert_trading_allowed(component="test", attempted_action="open_position")
    e = exc.value
    assert e.state == "SAFE_MODE"
    assert e.component == "test"
    assert e.attempted_action == "open_position"
    ev = e.as_evidence()
    assert ev["event"] == "execution_denied"
    assert ev["reason"] == "state_safe_mode"


def test_assert_trading_allowed_passes_in_healthy(reader_factory):
    set_default_reader_for_tests(reader_factory("HEALTHY"))
    decision = assert_trading_allowed(component="test", attempted_action="open_position")
    assert decision.allowed is True


def test_assert_critical_state_raises(reader_factory):
    set_default_reader_for_tests(reader_factory("CRITICAL"))
    with pytest.raises(TradingNotAllowed):
        assert_trading_allowed(component="x", attempted_action="y")


def test_assert_writes_denial_evidence_jsonl(reader_factory, tmp_path, monkeypatch):
    set_default_reader_for_tests(reader_factory("SAFE_MODE"))
    sink_calls: list[dict] = []
    with pytest.raises(TradingNotAllowed):
        assert_trading_allowed(
            component="comp",
            attempted_action="act",
            evidence_sink=sink_calls.append,
        )
    assert len(sink_calls) == 1
    assert sink_calls[0]["event"] == "execution_denied"
    assert sink_calls[0]["state"] == "SAFE_MODE"


# ── Policy projection ──────────────────────────────────────────────────


def test_policy_in_healthy_allows_everything(reader_factory):
    snap = reader_factory("HEALTHY").read()
    pol = derive_policy(snap)
    assert pol.trading_allowed
    assert pol.strategy_allowed
    assert pol.reconciliation_allowed
    assert pol.observability_allowed


def test_policy_in_safe_mode_denies_trading_keeps_observability(reader_factory):
    """I-S2..I-S5 — SAFE_MODE preserves recon and observability."""
    snap = reader_factory("SAFE_MODE").read()
    pol = derive_policy(snap)
    assert pol.trading_allowed is False
    assert pol.strategy_allowed is False
    assert pol.reconciliation_allowed is True
    assert pol.observability_allowed is True


def test_policy_in_critical_denies_trading_keeps_observability_best_effort(reader_factory):
    snap = reader_factory("CRITICAL").read()
    pol = derive_policy(snap)
    assert pol.trading_allowed is False
    assert pol.observability_allowed is True


def test_policy_in_degraded_still_allows_trading(reader_factory):
    """Per S1-05 table: DEGRADED keeps trading allowed (operator may tighten)."""
    snap = reader_factory("DEGRADED").read()
    pol = derive_policy(snap)
    assert pol.trading_allowed is True


def test_policy_strategy_denied_in_recovering(reader_factory):
    snap = reader_factory("RECOVERING").read()
    pol = derive_policy(snap)
    assert pol.strategy_allowed is False
