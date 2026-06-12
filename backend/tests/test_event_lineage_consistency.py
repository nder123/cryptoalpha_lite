from app.services.validation.event_lineage import LineageEvent, validate_event_lineage


def test_normal_chain_passes():
    events = [
        LineageEvent(event_id="event-1", trace_id="trace-1"),
        LineageEvent(event_id="event-2", trace_id="trace-1", parent_id="event-1"),
        LineageEvent(event_id="event-3", trace_id="trace-1", parent_id="event-2"),
    ]

    assert validate_event_lineage(events).passed


def test_broken_chain_fails():
    events = [
        LineageEvent(event_id="event-1", trace_id="trace-1"),
        LineageEvent(event_id="event-2", trace_id="trace-2", parent_id="event-1"),
    ]

    report = validate_event_lineage(events)

    assert not report.passed
    assert any(
        violation.code == "LINEAGE_BROKEN_CHAIN" for violation in report.violations
    )


def test_orphan_event_is_detected():
    events = [
        LineageEvent(
            event_id="event-2",
            trace_id="trace-1",
            parent_id="missing-parent",
        )
    ]

    report = validate_event_lineage(events)

    assert not report.passed
    assert any(
        violation.code == "LINEAGE_ORPHAN_EVENT" for violation in report.violations
    )
