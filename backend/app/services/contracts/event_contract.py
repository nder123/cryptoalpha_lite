"""Canonical event contract for the CryptoAlpha event system.

Every event flowing through execution_core, validation layer, and shadow
runtime MUST conform to this schema.  The contract is enforced at test time
(not runtime) so it adds zero overhead to the hot path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "event_type",
        "trace_id",
        "parent_id",
        "timestamp",
        "source_module",
    }
)


@dataclass(frozen=True)
class EventContract:
    """Canonical event envelope that all system events must satisfy."""

    event_type: str
    trace_id: str
    parent_id: Optional[str]
    timestamp: float
    source_module: str
    payload: Dict[str, Any]


def validate_event(raw: Dict[str, Any]) -> list[str]:
    """Return a list of violations for *raw* against the contract.

    An empty list means the event is conformant.
    """
    violations: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in raw:
            violations.append(f"missing required field: {field}")
    if "event_type" in raw and not isinstance(raw["event_type"], str):
        violations.append("event_type must be str")
    if "trace_id" in raw and not isinstance(raw["trace_id"], str):
        violations.append("trace_id must be str")
    if "timestamp" in raw and not isinstance(raw["timestamp"], (int, float)):
        violations.append("timestamp must be numeric")
    if "source_module" in raw and not isinstance(raw["source_module"], str):
        violations.append("source_module must be str")
    return violations


def validate_batch(events: Sequence[Dict[str, Any]]) -> Dict[int, list[str]]:
    """Validate a batch of events.  Returns ``{index: [violations]}`` for
    non-conformant entries only.  An empty dict means all events pass."""
    bad: Dict[int, list[str]] = {}
    for idx, event in enumerate(events):
        violations = validate_event(event)
        if violations:
            bad[idx] = violations
    return bad


def check_lineage_compatibility(
    events: Sequence[Dict[str, Any]],
) -> list[str]:
    """Verify trace-level lineage envelope compatibility.

    ``LineageSemantics.TRACE_LEVEL`` boundary:
    ``parent_id`` is interpreted as trace-level linkage. The invariant is
    "event belongs to trace graph consistency boundary", not event-to-event
    ancestry.

    Rules:
    * Every non-null ``parent_id`` must reference an existing ``trace_id``.
    * Root events (``parent_id is None``) are always valid.
    """
    trace_ids: set[str] = set()
    violations: list[str] = []
    for event in events:
        tid = event.get("trace_id")
        if isinstance(tid, str):
            trace_ids.add(tid)

    for idx, event in enumerate(events):
        pid = event.get("parent_id")
        if pid is not None and pid not in trace_ids:
            violations.append(
                f"event[{idx}] parent_id={pid!r} references unknown trace_id"
            )
    return violations
