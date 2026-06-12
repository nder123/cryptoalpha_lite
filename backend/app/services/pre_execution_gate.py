"""Passive pre-execution validation gate."""

from __future__ import annotations

from app.domain.events import CTOAiDecision, TradeAction
from app.services.runtime_enforcer import (
    RuntimeBoundaryDecision,
    RuntimeBoundaryEvent,
    RuntimeBoundaryResult,
    RuntimeBoundaryViolation,
    validate_boundary_compliance,
)

_DENY_ACTIONS = frozenset(
    {
        TradeAction.HOLD,
        TradeAction.REJECT,
        TradeAction.NO_TRADE,
    }
)


def validate_before_execution(decision: CTOAiDecision) -> RuntimeBoundaryResult:
    violations: list[RuntimeBoundaryViolation] = []
    trace_id = _metadata_text(decision, "trace_id")
    risk_event_id = _risk_origin(decision)
    parent_event_id = _parent_origin(decision)

    if trace_id is None:
        violations.append(
            RuntimeBoundaryViolation(
                code="TRACE_ID_MISSING",
                subject=decision.decision_uid,
                message="decision trace_id missing",
            )
        )

    if risk_event_id is None:
        violations.append(
            RuntimeBoundaryViolation(
                code="DECISION_WITHOUT_RISK",
                subject=decision.decision_uid,
                message="decision risk origin missing",
            )
        )

    if not decision.decision_uid:
        violations.append(
            RuntimeBoundaryViolation(
                code="DECISION_ORIGIN_INVALID",
                subject=decision.directive_id,
                message="decision_uid missing",
            )
        )

    if decision.directive_id != decision.directive.directive_id:
        violations.append(
            RuntimeBoundaryViolation(
                code="DECISION_ORIGIN_INVALID",
                subject=decision.decision_uid,
                message="decision directive_id does not match directive",
            )
        )

    if decision.directive.decision_uid != decision.decision_uid:
        violations.append(
            RuntimeBoundaryViolation(
                code="DECISION_ORIGIN_INVALID",
                subject=decision.decision_uid,
                message="decision_uid does not match directive origin",
            )
        )

    if decision.action != decision.directive.action:
        violations.append(
            RuntimeBoundaryViolation(
                code="DECISION_ORIGIN_INVALID",
                subject=decision.decision_uid,
                message="decision action does not match directive",
            )
        )

    if decision.action in _DENY_ACTIONS:
        violations.append(
            RuntimeBoundaryViolation(
                code="DECISION_NOT_EXECUTABLE",
                subject=decision.decision_uid,
                message="decision action does not authorize execution",
            )
        )

    if trace_id is not None and risk_event_id is not None:
        boundary_result = validate_boundary_compliance(
            [
                RuntimeBoundaryEvent(
                    event_id=parent_event_id,
                    trace_id=trace_id,
                    stage="input",
                ),
                RuntimeBoundaryEvent(
                    event_id=risk_event_id,
                    trace_id=trace_id,
                    stage="risk",
                    parent_id=parent_event_id,
                ),
            ],
            [
                RuntimeBoundaryDecision(
                    decision_id=decision.decision_uid,
                    trace_id=trace_id,
                    parent_event_id=parent_event_id,
                    risk_event_id=risk_event_id,
                    denied=decision.action in _DENY_ACTIONS,
                )
            ],
            [],
        )
        violations.extend(boundary_result.violations)

    items = tuple(violations)
    return RuntimeBoundaryResult(ok=not items, violations=items)


def is_execution_allowed(decision: CTOAiDecision) -> bool:
    return validate_before_execution(decision).ok


def _metadata_text(decision: CTOAiDecision, key: str) -> str | None:
    value = decision.meta.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _risk_origin(decision: CTOAiDecision) -> str | None:
    risk_event_id = _metadata_text(decision, "risk_event_id")
    if risk_event_id is not None:
        return risk_event_id
    return _metadata_text(decision, "risk_assessment_id")


def _parent_origin(decision: CTOAiDecision) -> str:
    parent_event_id = _metadata_text(decision, "parent_event_id")
    if parent_event_id is not None:
        return parent_event_id
    hypothesis_id = decision.directive.hypothesis_id
    if hypothesis_id:
        return f"input-{hypothesis_id}"
    return f"input-{decision.directive_id}"
