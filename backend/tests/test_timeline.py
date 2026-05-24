"""Tests for the operational timeline engine — S1-07."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.timeline.engine import (
    TimelineSources,
    correlate_incident,
    filter_by_severity,
    filter_by_source,
    filter_by_window,
    merge,
)
from runtime.timeline.events import (
    TIMELINE_EVENT_SCHEMA,
    TimelineEvent,
    parse_trading_gate_evidence,
    parse_transitions,
    _to_unix,
)


def _write(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for ln in lines:
            f.write(json.dumps(ln, sort_keys=True) + "\n")


def _transition(ts: float, frm: str, to: str) -> dict:
    return {
        "schema": "runtime_health_transition.v1",
        "transition_id": f"id-{ts}",
        "ts": ts,
        "from": frm,
        "to": to,
        "trigger": {"tier": 7, "predicate": "test", "probes": {}},
        "evidence": {"reasons": ["x"]},
        "consecutive_evaluations": 1,
        "elapsed_in_from_state_sec": 0.0,
        "loop_iteration": 1,
        "operator_acknowledged": False,
        "pid": 1,
        "recovery_actions": [],
    }


def _denial(ts: float, state: str = "SAFE_MODE") -> dict:
    return {
        "event": "execution_denied",
        "reason": f"state_{state.lower()}",
        "state": state,
        "component": "bybit_adapter",
        "attempted_action": "submit_Market_Buy_BTCUSDT",
        "stale": False,
        "ts": ts,
    }


# ── timestamp parsing ──────────────────────────────────────────────────


def test_to_unix_accepts_float_int_iso():
    from datetime import datetime, timezone
    assert _to_unix(1716553600.5) == 1716553600.5
    assert _to_unix(1716553600) == 1716553600.0
    iso = "2026-05-24T16:00:00+00:00"
    expected = datetime.fromisoformat(iso).timestamp()
    assert _to_unix(iso) == pytest.approx(expected, rel=1e-9)


def test_to_unix_handles_z_suffix():
    assert _to_unix("2026-05-24T16:00:00Z") is not None


def test_to_unix_returns_none_on_garbage():
    assert _to_unix("not-a-date") is None
    assert _to_unix("") is None
    assert _to_unix(None) is None


# ── parse_transitions ──────────────────────────────────────────────────


def test_parse_transitions_yields_events_with_severity(tmp_path):
    p = tmp_path / "transitions.jsonl"
    _write(p, [
        _transition(100.0, "HEALTHY", "DEGRADED"),
        _transition(200.0, "DEGRADED", "CRITICAL"),
        _transition(300.0, "CRITICAL", "SAFE_MODE"),
    ])
    events = list(parse_transitions(p))
    assert len(events) == 3
    assert events[0].severity == "notice"
    assert events[1].severity == "crit"
    assert events[2].severity == "alert"
    assert events[0].source == "transitions"
    assert events[0].kind == "state:HEALTHY->DEGRADED"


def test_parse_transitions_skips_malformed_lines(tmp_path):
    p = tmp_path / "transitions.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join([
        json.dumps(_transition(100.0, "HEALTHY", "DEGRADED")),
        "{not json",
        json.dumps({"no_ts": True}),  # no ts field
        json.dumps(_transition(200.0, "DEGRADED", "HEALTHY")),
    ]))
    events = list(parse_transitions(p))
    assert len(events) == 2


def test_parse_transitions_handles_missing_file(tmp_path):
    events = list(parse_transitions(tmp_path / "absent.jsonl"))
    assert events == []


# ── parse_trading_gate ─────────────────────────────────────────────────


def test_parse_trading_gate_marks_denials_alert(tmp_path):
    p = tmp_path / "gate.jsonl"
    _write(p, [_denial(150.0, "SAFE_MODE"), _denial(160.0, "CRITICAL")])
    events = list(parse_trading_gate_evidence(p))
    assert len(events) == 2
    assert all(e.severity == "alert" for e in events)
    assert all(e.source == "trading_gate" for e in events)


# ── merge: chronological ordering ──────────────────────────────────────


def test_merge_orders_by_timestamp(tmp_path):
    transitions = tmp_path / "artifacts" / "runtime_health_transitions.jsonl"
    gate = tmp_path / "artifacts" / "trading_gate_evidence.jsonl"
    _write(transitions, [_transition(100.0, "HEALTHY", "DEGRADED"), _transition(300.0, "DEGRADED", "HEALTHY")])
    _write(gate, [_denial(200.0)])

    sources = TimelineSources.for_repo(tmp_path)
    out = list(merge(sources))
    timestamps = [e.ts for e in out]
    assert timestamps == sorted(timestamps)
    assert [e.source for e in out] == ["transitions", "trading_gate", "transitions"]


def test_merge_works_with_only_one_source_present(tmp_path):
    transitions = tmp_path / "artifacts" / "runtime_health_transitions.jsonl"
    _write(transitions, [_transition(100.0, "HEALTHY", "DEGRADED")])
    sources = TimelineSources.for_repo(tmp_path)
    out = list(merge(sources))
    assert len(out) == 1


# ── filters ────────────────────────────────────────────────────────────


def test_filter_by_window_inclusive(tmp_path):
    events = [
        TimelineEvent(ts=100.0, ts_iso="", source="x", kind="a", payload={}),
        TimelineEvent(ts=150.0, ts_iso="", source="x", kind="b", payload={}),
        TimelineEvent(ts=200.0, ts_iso="", source="x", kind="c", payload={}),
    ]
    out = list(filter_by_window(events, since=120.0, until=180.0))
    assert [e.ts for e in out] == [150.0]


def test_filter_by_severity_threshold():
    events = [
        TimelineEvent(ts=1.0, ts_iso="", source="x", kind="a", payload={}, severity="info"),
        TimelineEvent(ts=2.0, ts_iso="", source="x", kind="b", payload={}, severity="warning"),
        TimelineEvent(ts=3.0, ts_iso="", source="x", kind="c", payload={}, severity="crit"),
    ]
    out = list(filter_by_severity(events, min_severity="warning"))
    assert {e.kind for e in out} == {"b", "c"}


def test_filter_by_source():
    events = [
        TimelineEvent(ts=1.0, ts_iso="", source="transitions", kind="a", payload={}),
        TimelineEvent(ts=2.0, ts_iso="", source="trading_gate", kind="b", payload={}),
    ]
    out = list(filter_by_source(events, sources=("trading_gate",)))
    assert [e.source for e in out] == ["trading_gate"]


# ── incident correlation ──────────────────────────────────────────────


def test_correlate_incident_finds_anchor_at_safe_mode(tmp_path):
    """Synthetic incident: HEALTHY → DEGRADED → CRITICAL → SAFE_MODE plus
    several denied executions after. Anchor = SAFE_MODE entry. Causal chain
    must include the prior CRITICAL transition and the subsequent denials."""
    transitions = tmp_path / "artifacts" / "runtime_health_transitions.jsonl"
    gate = tmp_path / "artifacts" / "trading_gate_evidence.jsonl"
    _write(transitions, [
        _transition(100.0, "HEALTHY", "DEGRADED"),
        _transition(150.0, "DEGRADED", "CRITICAL"),
        _transition(160.0, "CRITICAL", "SAFE_MODE"),
        _transition(900.0, "SAFE_MODE", "RECOVERING"),  # outside window
    ])
    _write(gate, [
        _denial(165.0),
        _denial(170.0),
        _denial(175.0),
    ])

    sources = TimelineSources.for_repo(tmp_path)
    events = list(merge(sources))
    inc = correlate_incident(events, anchor_ts=160.0, window_before_sec=120.0, window_after_sec=120.0)

    assert inc.anchor_kind == "state:CRITICAL->SAFE_MODE"
    assert inc.anchor_source == "transitions"
    chain_kinds = [e.kind for e in inc.causal_chain]
    assert "state:DEGRADED->CRITICAL" in chain_kinds  # cause
    assert "state:CRITICAL->SAFE_MODE" in chain_kinds  # anchor
    # consequences: at least one denied execution
    assert any(k.startswith("gate:execution_denied") for k in chain_kinds)
    # ordering must be chronological
    timestamps = [e.ts for e in inc.causal_chain]
    assert timestamps == sorted(timestamps)


def test_correlate_incident_empty_window(tmp_path):
    sources = TimelineSources.for_repo(tmp_path)
    events = list(merge(sources))  # empty
    inc = correlate_incident(events, anchor_ts=1000.0)
    assert inc.events == ()
    assert inc.causal_chain == ()
    assert inc.anchor_kind == "none"


def test_correlate_serialization_schema(tmp_path):
    transitions = tmp_path / "artifacts" / "runtime_health_transitions.jsonl"
    _write(transitions, [_transition(100.0, "HEALTHY", "CRITICAL")])
    sources = TimelineSources.for_repo(tmp_path)
    inc = correlate_incident(list(merge(sources)), anchor_ts=100.0)
    d = inc.to_dict()
    assert d["schema"] == "operational_incident.v1"
    assert d["anchor"]["kind"] == "state:HEALTHY->CRITICAL"
    assert d["events"][0]["schema"] == TIMELINE_EVENT_SCHEMA


# ── ts ordering stability under equal timestamps ──────────────────────


def test_merge_stable_on_equal_ts(tmp_path):
    transitions = tmp_path / "artifacts" / "runtime_health_transitions.jsonl"
    gate = tmp_path / "artifacts" / "trading_gate_evidence.jsonl"
    same_ts = 555.0
    _write(transitions, [_transition(same_ts, "HEALTHY", "DEGRADED")])
    _write(gate, [_denial(same_ts)])
    sources = TimelineSources.for_repo(tmp_path)
    out = list(merge(sources))
    assert [e.ts for e in out] == [same_ts, same_ts]
    # heapq.merge stable wrt our (ts, source, id) key
    sources_seen = [e.source for e in out]
    assert sources_seen == sorted(sources_seen)
