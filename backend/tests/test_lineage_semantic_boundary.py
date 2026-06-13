from app.services.contracts.event_contract import check_lineage_compatibility
from app.services.validation.event_lineage import LineageEvent, validate_event_lineage


def test_trace_level_and_event_level_lineage_diverge_intentionally():
    raw_events = [
        {
            "event_id": "A",
            "event_type": "synthetic",
            "trace_id": "T1",
            "parent_id": "X",
            "timestamp": 1.0,
            "source_module": "test",
        },
        {
            "event_id": "B",
            "event_type": "synthetic",
            "trace_id": "T1",
            "parent_id": "A",
            "timestamp": 2.0,
            "source_module": "test",
        },
    ]
    lineage_events = [
        LineageEvent(event_id="A", trace_id="T1", parent_id="X"),
        LineageEvent(event_id="B", trace_id="T1", parent_id="A"),
    ]

    event_contract_result = check_lineage_compatibility(raw_events)
    event_lineage_report = validate_event_lineage(lineage_events)
    event_lineage_result = [
        violation.code for violation in event_lineage_report.violations
    ]

    # Difference is intentional, not a bug:
    # event_contract is trace-level and does not validate the A -> B event chain.
    assert len(event_contract_result) == 2
    assert any("parent_id='X'" in violation for violation in event_contract_result)
    assert any("parent_id='A'" in violation for violation in event_contract_result)

    # event_lineage is event-level: A -> B is valid, while X -> A is missing.
    assert event_lineage_result == ["LINEAGE_ORPHAN_EVENT"]

    # Keep the semantic divergence explicit so future consolidation preserves it.
    assert event_contract_result != event_lineage_result
