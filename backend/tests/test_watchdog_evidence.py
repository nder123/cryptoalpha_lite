"""Tests for evidence writer (single-writer invariant artifacts)."""
from __future__ import annotations

import json
from pathlib import Path

from runtime.watchdog.evidence import (
    ARTIFACT_SCHEMA,
    HealthArtifact,
    TRANSITION_SCHEMA,
    TransitionRecord,
    append_transition,
    serialize_transition,
    write_artifact_atomic,
)
from runtime.watchdog.states import H


def test_transition_record_default_schema():
    r = TransitionRecord(from_state="HEALTHY", to_state="DEGRADED")
    d = serialize_transition(r)
    assert d["schema"] == TRANSITION_SCHEMA
    assert d["from"] == "HEALTHY"
    assert d["to"] == "DEGRADED"
    assert "transition_id" in d and len(d["transition_id"]) > 0
    assert "ts" in d
    assert "pid" in d and isinstance(d["pid"], int)


def test_artifact_default_schema_and_to_dict():
    a = HealthArtifact(
        state=H.DEGRADED,
        since="2026-05-24T13:00:00+03:00",
        previous_state=H.HEALTHY,
        transition_id="abc",
        reasons=["p5_fail"],
        probes={"P1": "pass"},
        recovery_mode=False,
        trading_enabled=True,
        runtime_mode="PAPER",
    )
    d = a.to_dict()
    assert d["schema"] == ARTIFACT_SCHEMA
    assert d["state"] == "DEGRADED"
    assert d["previous_state"] == "HEALTHY"


def test_write_artifact_atomic_creates_valid_json(tmp_path: Path):
    out = tmp_path / "runtime_health.json"
    a = HealthArtifact(
        state=H.HEALTHY,
        since="2026-05-24T13:00:00+03:00",
        previous_state=None,
        transition_id="x",
        reasons=[],
        probes={},
        recovery_mode=False,
        trading_enabled=True,
        runtime_mode="OFFLINE",
    )
    write_artifact_atomic(out, a)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["schema"] == ARTIFACT_SCHEMA
    assert data["state"] == "HEALTHY"


def test_write_artifact_leaves_no_temp_files(tmp_path: Path):
    out = tmp_path / "runtime_health.json"
    a = HealthArtifact(
        state=H.HEALTHY,
        since="x",
        previous_state=None,
        transition_id="x",
        reasons=[],
        probes={},
        recovery_mode=False,
        trading_enabled=True,
        runtime_mode="OFFLINE",
    )
    for _ in range(5):
        write_artifact_atomic(out, a)
    tmp_files = list(tmp_path.glob(".runtime_health_*"))
    assert tmp_files == []


def test_append_transition_appends_one_line_per_record(tmp_path: Path):
    out = tmp_path / "transitions.jsonl"
    for i in range(3):
        append_transition(
            out,
            TransitionRecord(from_state="HEALTHY", to_state="DEGRADED", loop_iteration=i),
        )
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert all(p["schema"] == TRANSITION_SCHEMA for p in parsed)
    assert [p["loop_iteration"] for p in parsed] == [0, 1, 2]
