"""Passive runtime boundary validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

RuntimeEventStage = Literal["input", "risk"]

SUCCESS_EXECUTION_STATUSES = frozenset(
    {
        "submitted",
        "partially_filled",
        "filled",
    }
)


@dataclass(frozen=True)
class RuntimeBoundaryEvent:
    event_id: str
    trace_id: str
    stage: RuntimeEventStage
    parent_id: str | None = None


@dataclass(frozen=True)
class RuntimeBoundaryDecision:
    decision_id: str
    trace_id: str
    parent_event_id: str
    risk_event_id: str
    denied: bool = False


@dataclass(frozen=True)
class RuntimeBoundaryExecution:
    execution_id: str
    trace_id: str
    decision_id: str | None
    status: str


@dataclass(frozen=True)
class RuntimeBoundaryViolation:
    code: str
    subject: str
    message: str


@dataclass(frozen=True)
class RuntimeBoundaryResult:
    ok: bool
    violations: tuple[RuntimeBoundaryViolation, ...]


def validate_trace_consistency(
    events: Sequence[RuntimeBoundaryEvent],
    decisions: Sequence[RuntimeBoundaryDecision],
    executions: Sequence[RuntimeBoundaryExecution],
) -> RuntimeBoundaryResult:
    violations: list[RuntimeBoundaryViolation] = []
    event_by_id = {event.event_id: event for event in events}
    event_order = {event.event_id: index for index, event in enumerate(events)}
    root_trace = _root_trace(events)

    for event in events:
        if not event.trace_id:
            violations.append(
                _violation("TRACE_ID_MISSING", event.event_id, "event trace_id missing")
            )
        elif root_trace and event.trace_id != root_trace:
            violations.append(
                _violation("TRACE_ID_MISMATCH", event.event_id, "event trace_id forked")
            )

        if event.parent_id is not None:
            parent = event_by_id.get(event.parent_id)
            if parent is None:
                violations.append(
                    _violation(
                        "EVENT_PARENT_MISSING",
                        event.event_id,
                        "event parent is not present in the trace",
                    )
                )
            elif parent.trace_id != event.trace_id:
                violations.append(
                    _violation(
                        "TRACE_ID_MISMATCH",
                        event.event_id,
                        "event parent trace_id differs",
                    )
                )
            elif event_order[parent.event_id] >= event_order[event.event_id]:
                violations.append(
                    _violation(
                        "EVENT_PARENT_ORDER",
                        event.event_id,
                        "event parent appears after child",
                    )
                )

    for decision in decisions:
        if not decision.trace_id:
            violations.append(
                _violation(
                    "TRACE_ID_MISSING",
                    decision.decision_id,
                    "decision trace_id missing",
                )
            )
            continue
        if root_trace and decision.trace_id != root_trace:
            violations.append(
                _violation(
                    "TRACE_ID_MISMATCH",
                    decision.decision_id,
                    "decision trace_id differs from input trace",
                )
            )

        parent = event_by_id.get(decision.parent_event_id)
        risk = event_by_id.get(decision.risk_event_id)
        if parent is None:
            violations.append(
                _violation(
                    "DECISION_WITHOUT_INPUT",
                    decision.decision_id,
                    "decision parent event is missing",
                )
            )
        elif parent.trace_id != decision.trace_id:
            violations.append(
                _violation(
                    "TRACE_ID_MISMATCH",
                    decision.decision_id,
                    "decision parent trace_id differs",
                )
            )
        if risk is None:
            violations.append(
                _violation(
                    "DECISION_WITHOUT_RISK",
                    decision.decision_id,
                    "decision risk event is missing",
                )
            )
        elif risk.trace_id != decision.trace_id:
            violations.append(
                _violation(
                    "TRACE_ID_MISMATCH",
                    decision.decision_id,
                    "decision risk trace_id differs",
                )
            )

    decision_by_id = {decision.decision_id: decision for decision in decisions}
    for execution in executions:
        if not execution.trace_id:
            violations.append(
                _violation(
                    "TRACE_ID_MISSING",
                    execution.execution_id,
                    "execution trace_id missing",
                )
            )
            continue
        if root_trace and execution.trace_id != root_trace:
            violations.append(
                _violation(
                    "TRACE_ID_MISMATCH",
                    execution.execution_id,
                    "execution trace_id differs from input trace",
                )
            )

        decision = (
            decision_by_id.get(execution.decision_id)
            if execution.decision_id is not None
            else None
        )
        if decision is not None and decision.trace_id != execution.trace_id:
            violations.append(
                _violation(
                    "TRACE_ID_MISMATCH",
                    execution.execution_id,
                    "execution decision trace_id differs",
                )
            )

    return _result(violations)


def validate_execution_origin(
    decisions: Sequence[RuntimeBoundaryDecision],
    executions: Sequence[RuntimeBoundaryExecution],
) -> RuntimeBoundaryResult:
    violations: list[RuntimeBoundaryViolation] = []
    decision_ids = {decision.decision_id for decision in decisions}

    for execution in executions:
        if not execution.decision_id:
            violations.append(
                _violation(
                    "EXECUTION_WITHOUT_DECISION",
                    execution.execution_id,
                    "execution has no decision origin",
                )
            )
        elif execution.decision_id not in decision_ids:
            violations.append(
                _violation(
                    "EXECUTION_WITHOUT_DECISION",
                    execution.execution_id,
                    "execution decision origin is missing",
                )
            )

    return _result(violations)


def validate_boundary_compliance(
    events: Sequence[RuntimeBoundaryEvent],
    decisions: Sequence[RuntimeBoundaryDecision],
    executions: Sequence[RuntimeBoundaryExecution],
) -> RuntimeBoundaryResult:
    violations = [
        *validate_trace_consistency(events, decisions, executions).violations,
        *validate_execution_origin(decisions, executions).violations,
    ]
    decision_by_id = {decision.decision_id: decision for decision in decisions}

    for execution in executions:
        if execution.decision_id is None:
            continue
        decision = decision_by_id.get(execution.decision_id)
        if decision is None:
            continue
        if decision.denied and _successful_status(execution.status):
            violations.append(
                _violation(
                    "DENIED_DECISION_SUCCESSFUL_EXECUTION",
                    execution.execution_id,
                    "denied decision reported successful execution",
                )
            )

    return _result(violations)


def _root_trace(events: Sequence[RuntimeBoundaryEvent]) -> str | None:
    for event in events:
        if event.parent_id is None:
            return event.trace_id
    return events[0].trace_id if events else None


def _successful_status(status: str) -> bool:
    return status.strip().lower() in SUCCESS_EXECUTION_STATUSES


def _violation(code: str, subject: str, message: str) -> RuntimeBoundaryViolation:
    return RuntimeBoundaryViolation(code=code, subject=subject, message=message)


def _result(violations: Sequence[RuntimeBoundaryViolation]) -> RuntimeBoundaryResult:
    items = tuple(violations)
    return RuntimeBoundaryResult(ok=not items, violations=items)
