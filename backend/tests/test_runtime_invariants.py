from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from app.core.runtime_config import RuntimeConfig
from app.domain.events import (
    CTOAiDecision,
    ExecutionReport,
    ExecutionStatus,
    HypothesisType,
    RiskAssessment,
    RiskDecision,
    TradeAction,
    TradeDirective,
    TradeHypothesis,
    TradingMode,
)
from app.services import execution_engine, risk_engine, trading_gate
from app.services.runtime_health_reader import (
    RuntimeHealthReader,
    RuntimeHealthSnapshot,
)

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TRACE_ID = "trace-runtime-invariants"
SUCCESS_EXECUTION_STATUSES = frozenset(
    {
        ExecutionStatus.SUBMITTED,
        ExecutionStatus.PARTIALLY_FILLED,
        ExecutionStatus.FILLED,
    }
)


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    trace_id: str
    parent_id: str | None
    payload: object


@dataclass(frozen=True)
class GateOutput:
    gate: trading_gate.GateDecision
    decision: CTOAiDecision
    risk: RiskAssessment


@dataclass(frozen=True)
class RuntimeOutputs:
    input_event: RuntimeEvent
    risk_event: RuntimeEvent
    decision_event: RuntimeEvent | None
    execution_event: RuntimeEvent | None


class RuntimeEventBus:
    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    def emit(self, event: RuntimeEvent) -> RuntimeEvent:
        self.events.append(event)
        return event


class RuntimeRiskEngine:
    def __init__(self) -> None:
        self._engine = risk_engine.RiskEngine.__new__(risk_engine.RiskEngine)
        self._engine._config = RuntimeConfig()

    def evaluate(self, event: RuntimeEvent) -> RuntimeEvent:
        hypothesis = cast(TradeHypothesis, event.payload)
        assessment = self._engine._assess_hypothesis(
            hypothesis,
            current_exposure=0.0,
            risk_budget={},
            daily_stats={
                "trades_today": 0.0,
                "pnl_today": 0.0,
                "consecutive_losses": 0.0,
            },
        )
        return RuntimeEvent(
            event_id="risk-checked",
            trace_id=event.trace_id,
            parent_id=event.event_id,
            payload=assessment,
        )


class HealthyRuntimeReader(RuntimeHealthReader):
    def read(self) -> RuntimeHealthSnapshot:
        return RuntimeHealthSnapshot(
            state="HEALTHY",
            stale=False,
            stale_reason=None,
            reasons=(),
            since=FIXED_NOW.isoformat(),
        )


class DeniedRuntimeReader(RuntimeHealthReader):
    def read(self) -> RuntimeHealthSnapshot:
        return RuntimeHealthSnapshot(
            state="SAFE_MODE",
            stale=False,
            stale_reason=None,
            reasons=("runtime contract deny path",),
            since=FIXED_NOW.isoformat(),
        )


class RuntimeTradingGate:
    def decide(
        self, event: RuntimeEvent, *, reader: RuntimeHealthReader
    ) -> RuntimeEvent:
        assessment = cast(RiskAssessment, event.payload)
        gate_decision = trading_gate.is_trading_allowed(reader=reader)
        action = TradeAction.OPEN
        quantity = 0.001
        notional = 50.0
        rationale = ["runtime contract risk approved"]

        if not gate_decision.allowed or assessment.decision is RiskDecision.BLOCKED:
            action = TradeAction.REJECT
            quantity = 0.0
            notional = 0.0
            rationale = ["runtime contract denied"]

        directive = TradeDirective(
            directive_id=f"dir-{assessment.assessment_id}",
            hypothesis_id=assessment.hypothesis_id,
            symbol=assessment.symbol,
            issued_at=FIXED_NOW,
            action=action,
            rationale=rationale,
            mode=TradingMode.MANUAL,
            confidence=0.75,
            direction="long",
            order_type="limit",
            quantity=quantity,
            price=50_000.0,
            leverage=1.0,
            notional_usdt=notional,
            take_profit_price=51_000.0,
            stop_loss_price=49_500.0,
            decision_uid=f"decision-{assessment.assessment_id}",
        )
        decision = CTOAiDecision(
            decision_uid=directive.decision_uid or "decision-runtime-invariants",
            directive_id=directive.directive_id,
            symbol=directive.symbol,
            issued_at=directive.issued_at,
            action=directive.action,
            size=directive.quantity,
            notional_usdt=directive.notional_usdt,
            source="fsm",
            meta={
                "trace_id": event.trace_id,
                "risk_assessment_id": assessment.assessment_id,
            },
            directive=directive,
        )

        return RuntimeEvent(
            event_id="decided",
            trace_id=event.trace_id,
            parent_id=event.event_id,
            payload=GateOutput(
                gate=gate_decision,
                decision=decision,
                risk=assessment,
            ),
        )


class RuntimeExecutionEngine:
    def execute(self, event: RuntimeEvent) -> RuntimeEvent:
        output = cast(GateOutput, event.payload)
        decision = output.decision
        status = ExecutionStatus.SUBMITTED
        notes = [
            "runtime contract execution result",
            f"decision_uid={decision.decision_uid}",
            f"trace_id={event.trace_id}",
        ]

        if (
            not output.gate.allowed
            or output.risk.decision is RiskDecision.BLOCKED
            or decision.action is TradeAction.REJECT
        ):
            status = ExecutionStatus.REJECTED
            notes = [
                "runtime contract execution rejected",
                f"decision_uid={decision.decision_uid}",
                f"trace_id={event.trace_id}",
            ]

        report = ExecutionReport(
            directive_id=decision.directive_id,
            symbol=decision.symbol,
            action=decision.action,
            status=status,
            quantity=decision.size,
            avg_price=decision.directive.price,
            fees_paid=0.0,
            reported_at=FIXED_NOW,
            notes=notes,
        )

        return RuntimeEvent(
            event_id="executed",
            trace_id=event.trace_id,
            parent_id=event.event_id,
            payload=report,
        )


def _input_event() -> RuntimeEvent:
    return RuntimeEvent(
        event_id="created",
        trace_id=TRACE_ID,
        parent_id=None,
        payload=TradeHypothesis(
            hypothesis_id="hyp-runtime-invariants",
            symbol="BTCUSDT",
            created_at=FIXED_NOW,
            hypothesis_type=HypothesisType.MOMENTUM,
            confidence=0.8,
            direction="long",
            entry_price=50_000.0,
            target_price=51_000.0,
            stop_price=49_500.0,
            position_size=0.001,
            leverage=1.0,
            notional_usdt=50.0,
            supporting_metrics={"volume_score": 1.0},
            notes=["runtime invariants"],
        ),
    )


def _run_contract(*, reader: RuntimeHealthReader) -> RuntimeOutputs:
    event_bus = RuntimeEventBus()
    input_event = event_bus.emit(_input_event())
    risk_event = event_bus.emit(RuntimeRiskEngine().evaluate(input_event))
    decision_event = event_bus.emit(
        RuntimeTradingGate().decide(risk_event, reader=reader)
    )
    execution_event = event_bus.emit(RuntimeExecutionEngine().execute(decision_event))

    return RuntimeOutputs(
        input_event=input_event,
        risk_event=risk_event,
        decision_event=decision_event,
        execution_event=execution_event,
    )


def _execution_trace_id(report: ExecutionReport) -> str | None:
    for note in report.notes:
        if note.startswith("trace_id="):
            return note.removeprefix("trace_id=")
    return None


def _validate_runtime_invariants(outputs: RuntimeOutputs) -> list[str]:
    violations: list[str] = []
    decision_event = outputs.decision_event
    execution_event = outputs.execution_event

    if decision_event is None:
        violations.append("decision_missing")
    elif decision_event.parent_id != outputs.risk_event.event_id:
        violations.append("decision_without_traceable_input")

    if execution_event is not None and decision_event is None:
        violations.append("execution_without_decision")
        return violations

    if execution_event is not None and decision_event is not None:
        if execution_event.parent_id != decision_event.event_id:
            violations.append("execution_without_decision")

        gate_output = cast(GateOutput, decision_event.payload)
        report = cast(ExecutionReport, execution_event.payload)

        if report.directive_id != gate_output.decision.directive_id:
            violations.append("execution_decision_mismatch")

        trace_ids = {
            outputs.input_event.trace_id,
            outputs.risk_event.trace_id,
            decision_event.trace_id,
            execution_event.trace_id,
            cast(str, gate_output.decision.meta["trace_id"]),
            _execution_trace_id(report),
        }
        if trace_ids != {outputs.input_event.trace_id}:
            violations.append("trace_id_mismatch")

        denied = (
            not gate_output.gate.allowed
            or gate_output.risk.decision is RiskDecision.BLOCKED
            or gate_output.decision.action is TradeAction.REJECT
        )
        if denied and report.status in SUCCESS_EXECUTION_STATUSES:
            violations.append("denied_decision_successfully_executed")

    return violations


def test_runtime_outputs_have_consistent_decision_and_execution_lineage():
    assert risk_engine.RiskEngine
    assert trading_gate.GateDecision
    assert execution_engine.ExecutionEngine

    outputs = _run_contract(reader=HealthyRuntimeReader())

    assert _validate_runtime_invariants(outputs) == []


def test_execution_result_without_decision_is_invalid():
    outputs = _run_contract(reader=HealthyRuntimeReader())

    invalid = RuntimeOutputs(
        input_event=outputs.input_event,
        risk_event=outputs.risk_event,
        decision_event=None,
        execution_event=outputs.execution_event,
    )

    assert "execution_without_decision" in _validate_runtime_invariants(invalid)


def test_decision_without_traceable_input_event_is_invalid():
    outputs = _run_contract(reader=HealthyRuntimeReader())
    assert outputs.decision_event is not None

    orphan_decision = RuntimeEvent(
        event_id=outputs.decision_event.event_id,
        trace_id=outputs.decision_event.trace_id,
        parent_id="missing-risk-event",
        payload=outputs.decision_event.payload,
    )
    invalid = RuntimeOutputs(
        input_event=outputs.input_event,
        risk_event=outputs.risk_event,
        decision_event=orphan_decision,
        execution_event=outputs.execution_event,
    )

    assert "decision_without_traceable_input" in _validate_runtime_invariants(invalid)


def test_trace_id_mismatch_across_event_decision_and_execution_is_invalid():
    outputs = _run_contract(reader=HealthyRuntimeReader())
    assert outputs.execution_event is not None

    mismatched_execution = RuntimeEvent(
        event_id=outputs.execution_event.event_id,
        trace_id="trace-runtime-invariants-mismatch",
        parent_id=outputs.execution_event.parent_id,
        payload=outputs.execution_event.payload,
    )
    invalid = RuntimeOutputs(
        input_event=outputs.input_event,
        risk_event=outputs.risk_event,
        decision_event=outputs.decision_event,
        execution_event=mismatched_execution,
    )

    assert "trace_id_mismatch" in _validate_runtime_invariants(invalid)


def test_denied_decision_must_not_report_successful_execution():
    outputs = _run_contract(reader=DeniedRuntimeReader())
    assert outputs.decision_event is not None
    assert outputs.execution_event is not None

    assert _validate_runtime_invariants(outputs) == []

    report = cast(ExecutionReport, outputs.execution_event.payload)
    invalid_report = report.model_copy(update={"status": ExecutionStatus.SUBMITTED})
    invalid_execution = RuntimeEvent(
        event_id=outputs.execution_event.event_id,
        trace_id=outputs.execution_event.trace_id,
        parent_id=outputs.execution_event.parent_id,
        payload=invalid_report,
    )
    invalid = RuntimeOutputs(
        input_event=outputs.input_event,
        risk_event=outputs.risk_event,
        decision_event=outputs.decision_event,
        execution_event=invalid_execution,
    )

    assert "denied_decision_successfully_executed" in _validate_runtime_invariants(
        invalid
    )
