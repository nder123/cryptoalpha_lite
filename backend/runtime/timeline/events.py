"""Unified TimelineEvent schema and source-specific parsers."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

TIMELINE_EVENT_SCHEMA = "operational_timeline_event.v1"


@dataclass(frozen=True)
class TimelineEvent:
    ts: float                       # unix seconds (canonical)
    ts_iso: str                     # ISO-8601 for human reading
    source: str                     # "transitions" | "trading_gate" | "retention" | "journald" | ...
    kind: str                       # short symbolic event class
    payload: dict[str, Any]         # raw record minus ts redundancy
    severity: str = "info"          # info | notice | warning | alert | crit

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TIMELINE_EVENT_SCHEMA,
            "ts": self.ts,
            "ts_iso": self.ts_iso,
            "source": self.source,
            "kind": self.kind,
            "severity": self.severity,
            "payload": dict(self.payload),
        }


def _to_unix(value: Any) -> float | None:
    """Best-effort timestamp parsing. Accepts unix float, int, ISO-8601 string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # try ISO-8601 with or without timezone
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            pass
        # try unix-as-string
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat()


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                yield obj


def parse_transitions(path: Path) -> Iterator[TimelineEvent]:
    """Parse artifacts/runtime_health_transitions.jsonl."""
    for rec in _iter_jsonl(path):
        ts = _to_unix(rec.get("ts"))
        if ts is None:
            continue
        to_state = str(rec.get("to") or "")
        severity = _severity_for_target_state(to_state)
        yield TimelineEvent(
            ts=ts,
            ts_iso=_to_iso(ts),
            source="transitions",
            kind=f"state:{rec.get('from', '?')}->{to_state}",
            payload=rec,
            severity=severity,
        )


def _severity_for_target_state(state: str) -> str:
    return {
        "HEALTHY": "info",
        "BOOTSTRAPPING": "info",
        "DEGRADED": "notice",
        "RECOVERING": "notice",
        "STALLED": "warning",
        "SAFE_MODE": "alert",
        "CRITICAL": "crit",
    }.get(state, "info")


def parse_trading_gate_evidence(path: Path) -> Iterator[TimelineEvent]:
    """Parse artifacts/trading_gate_evidence.jsonl."""
    for rec in _iter_jsonl(path):
        ts = _to_unix(rec.get("ts"))
        if ts is None:
            continue
        event = str(rec.get("event") or "execution_denied")
        severity = "alert" if event == "execution_denied" else "info"
        kind = f"gate:{event}"
        yield TimelineEvent(
            ts=ts,
            ts_iso=_to_iso(ts),
            source="trading_gate",
            kind=kind,
            payload=rec,
            severity=severity,
        )


def parse_retention_summary(path: Path) -> Iterator[TimelineEvent]:
    """Parse artifacts/retention_history.jsonl if it exists. v1 retention worker
    emits journald only; this parser accepts an optional sidecar log if the
    operator chooses to redirect summaries to a file."""
    for rec in _iter_jsonl(path):
        ts = _to_unix(rec.get("finished_at") or rec.get("started_at") or rec.get("ts"))
        if ts is None:
            continue
        deleted = rec.get("total_files_pruned", 0)
        rotated = len([r for r in rec.get("rotations", []) if r.get("rotated")])
        severity = "notice" if (deleted or rotated) else "info"
        yield TimelineEvent(
            ts=ts,
            ts_iso=_to_iso(ts),
            source="retention",
            kind=f"retention:pass(rot={rotated},del={deleted})",
            payload=rec,
            severity=severity,
        )


def parse_generic_jsonl(
    path: Path, *, source: str, ts_field: str = "ts", kind_prefix: str = "evt"
) -> Iterator[TimelineEvent]:
    """Generic JSONL adapter for any future stream."""
    for rec in _iter_jsonl(path):
        ts = _to_unix(rec.get(ts_field))
        if ts is None:
            continue
        kind = f"{kind_prefix}:{rec.get('event') or rec.get('kind') or 'unknown'}"
        yield TimelineEvent(
            ts=ts,
            ts_iso=_to_iso(ts),
            source=source,
            kind=kind,
            payload=rec,
        )
