"""Tests for event contract consistency."""

from __future__ import annotations

import time

from app.services.contracts.event_contract import (
    check_lineage_compatibility,
    validate_batch,
    validate_event,
)


def _valid_event(**overrides):
    base = {
        "event_type": "execution_report",
        "trace_id": "t-1",
        "parent_id": None,
        "timestamp": time.monotonic(),
        "source_module": "execution_engine",
    }
    base.update(overrides)
    return base


class TestAllEventsConformToContract:
    def test_conformant_events_pass(self):
        events = [
            _valid_event(trace_id="t-1"),
            _valid_event(trace_id="t-2", parent_id="t-1"),
            _valid_event(
                trace_id="t-3",
                parent_id="t-2",
                event_type="risk_assessment",
                source_module="risk_engine",
            ),
        ]
        bad = validate_batch(events)
        assert bad == {}

    def test_non_conformant_event_detected(self):
        events = [
            _valid_event(trace_id="t-1"),
            {"event_type": "bad_event"},  # missing required fields
        ]
        bad = validate_batch(events)
        assert 1 in bad
        violations = bad[1]
        assert any("trace_id" in v for v in violations)
        assert any("timestamp" in v for v in violations)
        assert any("source_module" in v for v in violations)


class TestNoSchemalessEvents:
    def test_extra_fields_allowed_but_required_enforced(self):
        event = _valid_event(extra_field="ok")
        assert validate_event(event) == []

    def test_wrong_types_rejected(self):
        event = _valid_event(event_type=123, timestamp="not-a-number")
        violations = validate_event(event)
        assert any("event_type must be str" in v for v in violations)
        assert any("timestamp must be numeric" in v for v in violations)


class TestLineageCompatibility:
    def test_valid_lineage(self):
        events = [
            _valid_event(trace_id="t-1", parent_id=None),
            _valid_event(trace_id="t-2", parent_id="t-1"),
            _valid_event(trace_id="t-3", parent_id="t-2"),
        ]
        assert check_lineage_compatibility(events) == []

    def test_broken_lineage_detected(self):
        events = [
            _valid_event(trace_id="t-1", parent_id=None),
            _valid_event(trace_id="t-2", parent_id="t-999"),
        ]
        violations = check_lineage_compatibility(events)
        assert len(violations) == 1
        assert "t-999" in violations[0]
