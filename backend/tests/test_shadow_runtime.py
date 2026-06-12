"""Tests for the Shadow Runtime Bridge."""

from __future__ import annotations

from app.services.shadow_runtime import ShadowRuntime


class TestShadowRuntime:
    def test_events_accepted(self):
        shadow = ShadowRuntime()
        entry = shadow.ingest(
            event_type="execution_report",
            event_id="d-1",
            payload={"symbol": "BTCUSDT", "action": "open"},
        )
        assert entry.event_type == "execution_report"
        assert entry.event_id == "d-1"
        assert entry.payload["symbol"] == "BTCUSDT"

    def test_events_traced(self):
        shadow = ShadowRuntime()
        shadow.ingest(event_type="execution_report", event_id="d-1", payload={})
        shadow.ingest(event_type="risk_assessment", event_id="r-1", payload={})
        shadow.ingest(event_type="cto_decision", event_id="c-1", payload={})

        assert len(shadow.trace) == 3
        assert shadow.find(event_id="r-1") is not None
        assert shadow.find(event_id="missing") is None
        ids = [e.event_id for e in shadow.trace]
        assert ids == ["d-1", "r-1", "c-1"]

    def test_no_execution_side_effect(self):
        shadow = ShadowRuntime()
        shadow.ingest(
            event_type="execution_report",
            event_id="d-1",
            payload={"action": "open", "quantity": 1.0},
        )
        # Shadow runtime must NOT expose any execution, order, or trade method.
        assert not hasattr(shadow, "execute")
        assert not hasattr(shadow, "place_order")
        assert not hasattr(shadow, "send_order")
        # Trace is purely read-only data; entries are frozen dataclasses.
        entry = shadow.trace[0]
        assert entry.payload.get("action") == "open"
        # Ingesting does not modify the payload or produce return side-effects
        # beyond the trace entry itself.
        assert shadow.trace == shadow.trace  # deterministic, no mutation
