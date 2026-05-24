"""Transition record writer — single-writer of the two artifacts.

Per docs/unified_health_state_machine_v1.md §6, §8 and docs/watchdog_recovery_v1.md §5.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .states import H

TRANSITION_SCHEMA = "runtime_health_transition.v1"
ARTIFACT_SCHEMA = "runtime_health.v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


@dataclass
class TransitionRecord:
    schema: str = TRANSITION_SCHEMA
    transition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=now_iso)
    from_state: str = ""
    to_state: str = ""
    trigger: dict[str, Any] = field(default_factory=dict)
    consecutive_evaluations: int = 0
    elapsed_in_from_state_sec: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    operator_acknowledged: bool = False
    recovery_actions: list[dict[str, Any]] = field(default_factory=list)
    pid: int = field(default_factory=os.getpid)
    loop_iteration: int = 0


def serialize_transition(rec: TransitionRecord) -> dict[str, Any]:
    d = asdict(rec)
    # Rename Python-friendly fields back to schema names.
    d["from"] = d.pop("from_state")
    d["to"] = d.pop("to_state")
    return d


@dataclass
class HealthArtifact:
    state: H
    since: str
    previous_state: H | None
    transition_id: str
    reasons: list[str]
    probes: dict[str, str]
    recovery_mode: bool
    trading_enabled: bool
    runtime_mode: str
    operator_acknowledged: bool = False
    next_evaluation_at: str | None = None
    evaluation_cadence_sec: int = 10
    schema: str = ARTIFACT_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "state": self.state.value,
            "since": self.since,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "transition_id": self.transition_id,
            "reasons": list(self.reasons),
            "probes": dict(self.probes),
            "recovery_mode": self.recovery_mode,
            "trading_enabled": self.trading_enabled,
            "runtime_mode": self.runtime_mode,
            "operator_acknowledged": self.operator_acknowledged,
            "next_evaluation_at": self.next_evaluation_at,
            "evaluation_cadence_sec": self.evaluation_cadence_sec,
        }


def write_artifact_atomic(path: Path, artifact: HealthArtifact) -> None:
    """Atomic write: temp file in same dir + fsync + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".runtime_health_", suffix=".json.tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(artifact.to_dict(), f, ensure_ascii=False, sort_keys=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def append_transition(path: Path, record: TransitionRecord) -> None:
    """Append a transition record as one JSON line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(serialize_transition(record), ensure_ascii=False, sort_keys=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


def emit_journald(tag: str, payload: dict[str, Any]) -> None:
    """Best-effort journald emission. Never raises."""
    import subprocess

    try:
        proc = subprocess.Popen(
            ["systemd-cat", "-t", tag],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            timeout=2,
        )
    except Exception:
        pass


def write_transition_atomic_set(
    *,
    transitions_jsonl: Path,
    health_json: Path,
    record: TransitionRecord,
    artifact: HealthArtifact,
    journald_tag: str = "cryptoalpha-watchdog",
) -> None:
    """Three-target write per §5: jsonl → json → journald.

    Order is fixed. Failures in (2) or (3) do not block (1).
    """
    append_transition(transitions_jsonl, record)
    try:
        write_artifact_atomic(health_json, artifact)
    except Exception:
        emit_journald(journald_tag, {"event": "artifact_write_failed", **serialize_transition(record)})
        raise
    emit_journald(journald_tag, serialize_transition(record))
