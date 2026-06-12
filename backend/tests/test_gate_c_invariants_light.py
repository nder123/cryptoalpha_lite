from app.domain.events import ExecutionStatus, TradeAction
from app.services.validation.gate_c_invariants import (
    GateCEvent,
    GateCState,
    validate_gate_c_invariants,
)


def _event(message_id: str, state: GateCState, source: str = "execution_engine"):
    return GateCEvent(
        trade_id="trade-1",
        state=state,
        message_id=message_id,
        source=source,
    )


def test_execution_engine_imports_and_lifecycle_is_valid():
    import app.services.execution_engine  # noqa: F401

    events = [
        _event("1-1", GateCState.CREATED, "execution_engine"),
        _event("1-2", GateCState.RISK_CHECKED, "risk_engine"),
        _event("1-3", GateCState.DECIDED, "trading_gate"),
        _event("1-4", GateCState.RECORDED, "execution_engine"),
    ]

    assert validate_gate_c_invariants(events).passed


def test_event_bus_sequence_has_no_gaps():
    events = [
        _event("1-1", GateCState.CREATED),
        _event("1-2", GateCState.RISK_CHECKED, "risk_engine"),
        _event("1-3", GateCState.DECIDED, "trading_gate"),
        _event("1-4", GateCState.RECORDED),
    ]

    assert validate_gate_c_invariants(events).passed


def test_trading_gate_never_decides_without_risk_check():
    events = [
        _event("1-1", GateCState.CREATED),
        _event("1-2", GateCState.DECIDED, "trading_gate"),
        _event("1-3", GateCState.RECORDED),
    ]

    report = validate_gate_c_invariants(events)

    assert not report.passed
    assert any(v.code == "GATE_C_DECISION_WITHOUT_RISK" for v in report.violations)


def test_event_bus_rejects_orphan_events():
    events = [
        GateCEvent(
            trade_id="",
            state=GateCState.CREATED,
            message_id="1-1",
            source="event_bus",
        )
    ]

    report = validate_gate_c_invariants(events)

    assert not report.passed
    assert any(v.code == "GATE_C_ORPHAN_EVENT" for v in report.violations)


def test_lifecycle_uses_known_execution_domain_states():
    assert TradeAction.OPEN.value == "open"
    assert ExecutionStatus.FILLED.value == "filled"
