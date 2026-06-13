from app.services.contracts.event_contract import (
    check_lineage_compatibility,
    validate_batch,
)
from app.services.validation.contract_registry import ContractRegistry
from app.services.validation.core import ValidationCore, ValidationResult
from app.services.validation.cross_module_consistency import (
    check_event_bus_coverage,
    check_event_contract,
    check_lineage_coverage,
    check_risk_coverage,
)
from app.services.validation.event_lineage import LineageEvent, validate_event_lineage


def test_controlled_pilot_trace_pipeline_completes_with_trace_integrity():
    decision_id = "decision-controlled-pilot"
    execution_id = "execution-controlled-pilot"
    decision_payload = {
        "trace_id": "trace-controlled-pilot-decision",
        "decision": "ALLOW",
    }
    raw_events = [
        _raw_event("pilot_input", "trace-controlled-pilot-input", None),
        (
            _raw_event(
                "pilot_risk",
                "trace-controlled-pilot-risk",
                "trace-controlled-pilot-input",
            )
        ),
        (
            _raw_event(
                "pilot_decision",
                "trace-controlled-pilot-decision",
                "trace-controlled-pilot-risk",
            )
        ),
    ]
    event_lineage = [
        LineageEvent(
            event_id="event-controlled-pilot-input",
            trace_id="trace-controlled-pilot",
        ),
        LineageEvent(
            event_id="event-controlled-pilot-risk",
            trace_id="trace-controlled-pilot",
            parent_id="event-controlled-pilot-input",
        ),
        LineageEvent(
            event_id="event-controlled-pilot-decision",
            trace_id="trace-controlled-pilot",
            parent_id="event-controlled-pilot-risk",
        ),
    ]

    event_contract_result = validate_batch(raw_events)
    contract_result = ContractRegistry().evaluate(decision_payload)
    trace_lineage_result = check_lineage_compatibility(raw_events)
    event_lineage_report = validate_event_lineage(event_lineage)
    event_contract_consistency = check_event_contract(raw_events)
    risk_coverage = check_risk_coverage([decision_id], {decision_id: {}})
    event_bus_coverage = check_event_bus_coverage([execution_id], {execution_id: {}})
    lineage_coverage = check_lineage_coverage(
        [decision_id],
        {decision_id: {"event_id": "event-controlled-pilot-decision"}},
    )
    final_decision = ValidationCore().evaluate(decision_payload, context={})

    assert event_contract_result == {}
    assert contract_result == {"valid": True, "violations": []}
    assert trace_lineage_result == []
    assert event_lineage_report.passed is True
    assert event_contract_consistency.ok is True
    assert risk_coverage.ok is True
    assert event_bus_coverage.ok is True
    assert lineage_coverage.ok is True
    assert final_decision == ValidationResult(allowed=True)


def _raw_event(
    event_type: str, trace_id: str, parent_id: str | None
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "trace_id": trace_id,
        "parent_id": parent_id,
        "timestamp": 1.0,
        "source_module": "controlled_pilot_harness",
    }
