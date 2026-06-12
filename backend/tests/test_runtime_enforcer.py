from app.services.runtime_enforcer import (
    RuntimeBoundaryDecision,
    RuntimeBoundaryEvent,
    RuntimeBoundaryExecution,
    validate_boundary_compliance,
    validate_execution_origin,
    validate_trace_consistency,
)

TRACE_ID = "trace-runtime-enforcer"


def _events(trace_id: str = TRACE_ID) -> list[RuntimeBoundaryEvent]:
    return [
        RuntimeBoundaryEvent(
            event_id="created",
            trace_id=trace_id,
            stage="input",
        ),
        RuntimeBoundaryEvent(
            event_id="risk-checked",
            trace_id=trace_id,
            stage="risk",
            parent_id="created",
        ),
    ]


def _decision(trace_id: str = TRACE_ID, *, denied: bool = False):
    return RuntimeBoundaryDecision(
        decision_id="decision-1",
        trace_id=trace_id,
        parent_event_id="created",
        risk_event_id="risk-checked",
        denied=denied,
    )


def _execution(
    trace_id: str = TRACE_ID,
    *,
    decision_id: str | None = "decision-1",
    status: str = "submitted",
):
    return RuntimeBoundaryExecution(
        execution_id="execution-1",
        trace_id=trace_id,
        decision_id=decision_id,
        status=status,
    )


def test_runtime_enforcer_accepts_valid_boundary_trace():
    events = _events()
    decisions = [_decision()]
    executions = [_execution()]

    assert validate_trace_consistency(events, decisions, executions).ok
    assert validate_execution_origin(decisions, executions).ok
    assert validate_boundary_compliance(events, decisions, executions).ok


def test_trace_consistency_detects_trace_id_fork():
    result = validate_trace_consistency(
        _events(),
        [_decision(trace_id="forked-trace")],
        [_execution()],
    )

    assert not result.ok
    assert any(violation.code == "TRACE_ID_MISMATCH" for violation in result.violations)


def test_execution_origin_rejects_direct_execution_without_decision():
    result = validate_execution_origin([], [_execution(decision_id=None)])

    assert not result.ok
    assert any(
        violation.code == "EXECUTION_WITHOUT_DECISION"
        for violation in result.violations
    )


def test_boundary_compliance_rejects_denied_decision_with_successful_execution():
    result = validate_boundary_compliance(
        _events(),
        [_decision(denied=True)],
        [_execution(status="filled")],
    )

    assert not result.ok
    assert any(
        violation.code == "DENIED_DECISION_SUCCESSFUL_EXECUTION"
        for violation in result.violations
    )


def test_boundary_compliance_allows_denied_decision_with_rejected_execution():
    result = validate_boundary_compliance(
        _events(),
        [_decision(denied=True)],
        [_execution(status="rejected")],
    )

    assert result.ok
