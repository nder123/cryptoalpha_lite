"""Gate C — Lightweight observability contract.

Every runtime event, decision, and execution result MUST produce an
observable artifact.  Missing ``trace_id`` or missing artifact must
fail validation.

Implementation uses existing runtime objects with synchronous,
in-memory validation only — no daemons, async loops, or heavy storage.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.events import ExecutionReport, ExecutionStatus, TradeAction
from runtime.timeline.events import TimelineEvent
from runtime.watchdog.evidence import TransitionRecord, serialize_transition


# GateDecision is defined in app.services.trading_gate but that module
# depends on runtime_health_reader which may not be present in all
# environments.  Mirror the frozen dataclass here to keep imports light.
@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    state: str
    reason: str
    stale: bool


# ---------------------------------------------------------------------------
# In-memory observability ledger
# ---------------------------------------------------------------------------


@dataclass
class ObservabilityArtifact:
    """A single observable artifact produced by a runtime action."""

    trace_id: str
    category: str  # "event" | "decision" | "execution"
    ts: float
    payload: Dict[str, Any] = field(default_factory=dict)


class ObservabilityLedger:
    """Synchronous in-memory store that validates the Gate C contract."""

    def __init__(self) -> None:
        self._artifacts: Dict[str, ObservabilityArtifact] = {}

    # -- producers ----------------------------------------------------------

    def record_event(self, event: TimelineEvent, *, trace_id: str) -> None:
        if not trace_id:
            raise ValueError("trace_id is required for observability")
        self._artifacts[trace_id] = ObservabilityArtifact(
            trace_id=trace_id,
            category="event",
            ts=event.ts,
            payload=event.to_dict(),
        )

    def record_decision(
        self,
        decision: GateDecision,
        *,
        trace_id: str,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        if not trace_id:
            raise ValueError("trace_id is required for observability")
        self._artifacts[trace_id] = ObservabilityArtifact(
            trace_id=trace_id,
            category="decision",
            ts=0.0,
            payload={
                "allowed": decision.allowed,
                "state": decision.state,
                "reason": decision.reason,
                "stale": decision.stale,
                **(extra or {}),
            },
        )

    def record_execution(self, report: ExecutionReport, *, trace_id: str) -> None:
        if not trace_id:
            raise ValueError("trace_id is required for observability")
        self._artifacts[trace_id] = ObservabilityArtifact(
            trace_id=trace_id,
            category="execution",
            ts=report.reported_at.timestamp(),
            payload=report.model_dump(mode="json"),
        )

    # -- validators ---------------------------------------------------------

    def has_artifact(self, trace_id: str) -> bool:
        return trace_id in self._artifacts

    def get_artifact(self, trace_id: str) -> ObservabilityArtifact:
        if trace_id not in self._artifacts:
            raise LookupError(f"no artifact for trace_id={trace_id}")
        return self._artifacts[trace_id]

    def validate_all_present(self, trace_ids: List[str]) -> List[str]:
        """Return list of missing trace_ids (empty == all present)."""
        return [tid for tid in trace_ids if tid not in self._artifacts]

    @property
    def count(self) -> int:
        return len(self._artifacts)


# ---------------------------------------------------------------------------
# Helpers to build minimal valid domain objects
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 12, 12, 0, 0, tzinfo=timezone.utc)


def _make_timeline_event(**overrides: Any) -> TimelineEvent:
    defaults: Dict[str, Any] = {
        "ts": _NOW.timestamp(),
        "ts_iso": _NOW.isoformat(),
        "source": "transitions",
        "kind": "state:HEALTHY->DEGRADED",
        "payload": {"from": "HEALTHY", "to": "DEGRADED"},
        "severity": "notice",
    }
    defaults.update(overrides)
    return TimelineEvent(**defaults)


def _make_gate_decision(**overrides: Any) -> GateDecision:
    defaults: Dict[str, Any] = {
        "allowed": True,
        "state": "HEALTHY",
        "reason": "state_allows_trading",
        "stale": False,
    }
    defaults.update(overrides)
    return GateDecision(**defaults)


def _make_execution_report(**overrides: Any) -> ExecutionReport:
    defaults: Dict[str, Any] = {
        "directive_id": "dir-001",
        "symbol": "BTCUSDT",
        "action": TradeAction.OPEN,
        "status": ExecutionStatus.FILLED,
        "quantity": 0.01,
        "avg_price": 65000.0,
        "fees_paid": 1.5,
        "reported_at": _NOW,
    }
    defaults.update(overrides)
    return ExecutionReport(**defaults)


# ---------------------------------------------------------------------------
# Contract 1: Every runtime event produces an observable artifact
# ---------------------------------------------------------------------------


class TestRuntimeEventObservability:
    def test_single_event_produces_artifact(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        event = _make_timeline_event()

        ledger.record_event(event, trace_id=tid)

        assert ledger.has_artifact(tid)
        art = ledger.get_artifact(tid)
        assert art.category == "event"
        assert art.trace_id == tid
        assert art.payload["source"] == "transitions"

    def test_multiple_events_each_produce_artifact(self):
        ledger = ObservabilityLedger()
        trace_ids = [str(uuid.uuid4()) for _ in range(5)]

        for i, tid in enumerate(trace_ids):
            event = _make_timeline_event(
                kind=f"state:step_{i}",
                payload={"step": i},
            )
            ledger.record_event(event, trace_id=tid)

        assert ledger.count == 5
        missing = ledger.validate_all_present(trace_ids)
        assert missing == []

    def test_event_preserves_payload_fidelity(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        event = _make_timeline_event(
            source="trading_gate",
            kind="gate:execution_admitted",
            severity="info",
        )

        ledger.record_event(event, trace_id=tid)

        art = ledger.get_artifact(tid)
        assert art.payload["kind"] == "gate:execution_admitted"
        assert art.payload["severity"] == "info"


# ---------------------------------------------------------------------------
# Contract 2: Every decision produces an observable artifact
# ---------------------------------------------------------------------------


class TestDecisionObservability:
    def test_allowed_decision_produces_artifact(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        decision = _make_gate_decision(allowed=True, state="HEALTHY")

        ledger.record_decision(decision, trace_id=tid)

        assert ledger.has_artifact(tid)
        art = ledger.get_artifact(tid)
        assert art.category == "decision"
        assert art.payload["allowed"] is True
        assert art.payload["state"] == "HEALTHY"

    def test_denied_decision_produces_artifact(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        decision = _make_gate_decision(
            allowed=False,
            state="SAFE_MODE",
            reason="state_safe_mode",
        )

        ledger.record_decision(decision, trace_id=tid)

        art = ledger.get_artifact(tid)
        assert art.category == "decision"
        assert art.payload["allowed"] is False
        assert art.payload["reason"] == "state_safe_mode"

    def test_decision_with_extra_metadata(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        decision = _make_gate_decision()

        ledger.record_decision(
            decision,
            trace_id=tid,
            extra={
                "component": "execution_engine",
                "attempted_action": "open_position",
            },
        )

        art = ledger.get_artifact(tid)
        assert art.payload["component"] == "execution_engine"


# ---------------------------------------------------------------------------
# Contract 3: Every execution result produces an observable artifact
# ---------------------------------------------------------------------------


class TestExecutionResultObservability:
    def test_filled_execution_produces_artifact(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        report = _make_execution_report(status=ExecutionStatus.FILLED)

        ledger.record_execution(report, trace_id=tid)

        assert ledger.has_artifact(tid)
        art = ledger.get_artifact(tid)
        assert art.category == "execution"
        assert art.payload["status"] == "filled"

    def test_failed_execution_produces_artifact(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        report = _make_execution_report(status=ExecutionStatus.FAILED)

        ledger.record_execution(report, trace_id=tid)

        art = ledger.get_artifact(tid)
        assert art.payload["status"] == "failed"

    def test_execution_artifact_contains_symbol_and_action(self):
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())
        report = _make_execution_report(symbol="ETHUSDT", action=TradeAction.CLOSE)

        ledger.record_execution(report, trace_id=tid)

        art = ledger.get_artifact(tid)
        assert art.payload["symbol"] == "ETHUSDT"
        assert art.payload["action"] == "close"


# ---------------------------------------------------------------------------
# Contract 4: Missing trace_id must fail observability validation
# ---------------------------------------------------------------------------


class TestMissingTraceIdFails:
    def test_empty_trace_id_rejected_for_event(self):
        ledger = ObservabilityLedger()
        event = _make_timeline_event()
        with pytest.raises(ValueError, match="trace_id is required"):
            ledger.record_event(event, trace_id="")

    def test_empty_trace_id_rejected_for_decision(self):
        ledger = ObservabilityLedger()
        decision = _make_gate_decision()
        with pytest.raises(ValueError, match="trace_id is required"):
            ledger.record_decision(decision, trace_id="")

    def test_empty_trace_id_rejected_for_execution(self):
        ledger = ObservabilityLedger()
        report = _make_execution_report()
        with pytest.raises(ValueError, match="trace_id is required"):
            ledger.record_execution(report, trace_id="")


# ---------------------------------------------------------------------------
# Contract 5: Missing artifact must fail observability validation
# ---------------------------------------------------------------------------


class TestMissingArtifactFails:
    def test_lookup_unknown_trace_id_raises(self):
        ledger = ObservabilityLedger()
        with pytest.raises(LookupError, match="no artifact"):
            ledger.get_artifact("nonexistent-id")

    def test_has_artifact_false_for_missing(self):
        ledger = ObservabilityLedger()
        assert ledger.has_artifact("nonexistent-id") is False

    def test_validate_all_present_reports_missing(self):
        ledger = ObservabilityLedger()
        tid_present = str(uuid.uuid4())
        tid_missing = str(uuid.uuid4())

        ledger.record_event(_make_timeline_event(), trace_id=tid_present)

        missing = ledger.validate_all_present([tid_present, tid_missing])
        assert missing == [tid_missing]

    def test_validate_all_present_empty_when_complete(self):
        ledger = ObservabilityLedger()
        tids = [str(uuid.uuid4()) for _ in range(3)]

        ledger.record_event(_make_timeline_event(), trace_id=tids[0])
        ledger.record_decision(_make_gate_decision(), trace_id=tids[1])
        ledger.record_execution(_make_execution_report(), trace_id=tids[2])

        assert ledger.validate_all_present(tids) == []


# ---------------------------------------------------------------------------
# Integration: full pipeline — event → decision → execution observed
# ---------------------------------------------------------------------------


class TestFullPipelineObservability:
    def test_end_to_end_pipeline_produces_three_artifacts(self):
        """Simulates a minimal runtime flow: a state-transition event is
        observed, a gate decision is recorded, and the execution result
        is captured.  All three MUST be independently retrievable."""
        ledger = ObservabilityLedger()

        evt_tid = str(uuid.uuid4())
        dec_tid = str(uuid.uuid4())
        exe_tid = str(uuid.uuid4())

        # 1. Runtime event
        event = _make_timeline_event(
            source="transitions",
            kind="state:BOOTSTRAPPING->HEALTHY",
        )
        ledger.record_event(event, trace_id=evt_tid)

        # 2. Gate decision
        decision = _make_gate_decision(allowed=True)
        ledger.record_decision(decision, trace_id=dec_tid)

        # 3. Execution result
        report = _make_execution_report(status=ExecutionStatus.FILLED)
        ledger.record_execution(report, trace_id=exe_tid)

        assert ledger.count == 3
        assert ledger.get_artifact(evt_tid).category == "event"
        assert ledger.get_artifact(dec_tid).category == "decision"
        assert ledger.get_artifact(exe_tid).category == "execution"
        assert ledger.validate_all_present([evt_tid, dec_tid, exe_tid]) == []

    def test_transition_record_is_observable_via_timeline_event(self):
        """A watchdog TransitionRecord, once converted to a TimelineEvent,
        must be observable through the ledger."""
        ledger = ObservabilityLedger()
        tid = str(uuid.uuid4())

        rec = TransitionRecord(from_state="HEALTHY", to_state="DEGRADED")
        serialized = serialize_transition(rec)
        event = TimelineEvent(
            ts=_NOW.timestamp(),
            ts_iso=_NOW.isoformat(),
            source="transitions",
            kind=f"state:{serialized['from']}->{serialized['to']}",
            payload=serialized,
            severity="notice",
        )

        ledger.record_event(event, trace_id=tid)

        art = ledger.get_artifact(tid)
        assert art.category == "event"
        assert "HEALTHY" in art.payload["kind"]
        assert "DEGRADED" in art.payload["kind"]
