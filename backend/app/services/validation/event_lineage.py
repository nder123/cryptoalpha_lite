from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineageEvent:
    event_id: str
    trace_id: str
    parent_id: str | None = None


@dataclass(frozen=True)
class LineageViolation:
    code: str
    message: str
    event_id: str | None = None


@dataclass(frozen=True)
class LineageReport:
    violations: tuple[LineageViolation, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.violations


def validate_event_lineage(events: list[LineageEvent]) -> LineageReport:
    """Validate event-level lineage ancestry.

    ``LineageSemantics.EVENT_LEVEL`` boundary:
    ``parent_id`` is interpreted as event ancestry linkage. The invariant is a
    strict DAG over ``event_id`` space; this function enforces parent existence
    and trace consistency as a secondary invariant.
    """
    violations: list[LineageViolation] = []
    by_id = {event.event_id: event for event in events if event.event_id}

    for event in events:
        if not event.event_id or not event.trace_id:
            violations.append(
                LineageViolation(
                    code="LINEAGE_ORPHAN_EVENT",
                    message="event is missing event_id or trace_id",
                    event_id=event.event_id or None,
                )
            )
            continue
        if event.parent_id is None:
            continue
        parent = by_id.get(event.parent_id)
        if parent is None:
            violations.append(
                LineageViolation(
                    code="LINEAGE_ORPHAN_EVENT",
                    message=f"{event.event_id} references missing parent {event.parent_id}",
                    event_id=event.event_id,
                )
            )
            continue
        if parent.trace_id != event.trace_id:
            violations.append(
                LineageViolation(
                    code="LINEAGE_BROKEN_CHAIN",
                    message=f"{event.event_id} crosses trace boundary from {event.trace_id}",
                    event_id=event.event_id,
                )
            )

    return LineageReport(tuple(violations))


def assert_event_lineage(events: list[LineageEvent]) -> None:
    report = validate_event_lineage(events)
    if not report.passed:
        details = "; ".join(violation.message for violation in report.violations)
        raise AssertionError(details)
