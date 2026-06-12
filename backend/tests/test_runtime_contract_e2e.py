from __future__ import annotations

from dataclasses import dataclass, replace
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
from app.infrastructure import event_bus as event_bus_module
from app.services import execution_engine, risk_engine, trading_gate
from app.services.runtime_health_reader import (
    RuntimeHealthReader,
    RuntimeHealthSnapshot,
)

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TRACE_ID = "trace-runtime-contract-1"


@dataclass(frozen=True)
class RuntimeContractEvent:
    event_id: str
    trace_id: str
    parent_id: str | None
    payload: object


class RuntimeContractEventBus:
    def __init__(self) -> None:
        self.events: list[RuntimeContractEvent] = []

    def emit(self, event: RuntimeContractEvent) -> RuntimeContractEvent:
        self.events.append(event)
        return event


class RuntimeContractRiskEngine:
    def __init__(self) -> None:
        self._engine = risk_engine.RiskEngine.__new__(risk_engine.RiskEngine)
        self._engine._config = RuntimeConfig()

    def evaluate(self, event: RuntimeContractEvent) -> RuntimeContractEvent:
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
        return RuntimeContractEvent(
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


class RuntimeContractTradingGate:
    def decide(self, event: RuntimeContractEvent) -> RuntimeContractEvent:
        assessment = cast(RiskAssessment, event.payload)
        gate_decision = trading_gate.is_trading_allowed(reader=HealthyRuntimeReader())

        assert gate_decision.allowed
        assert assessment.decision is RiskDecision.APPROVED

        directive = TradeDirective(
            directive_id=f"dir-{assessment.assessment_id}",
            hypothesis_id=assessment.hypothesis_id,
            symbol=assessment.symbol,
            issued_at=FIXED_NOW,
            action=TradeAction.OPEN,
            rationale=["runtime contract risk approved"],
            mode=TradingMode.MANUAL,
            confidence=0.75,
            direction="long",
            order_type="limit",
            quantity=0.001,
            price=50_000.0,
            leverage=1.0,
            notional_usdt=50.0,
            take_profit_price=51_000.0,
            stop_loss_price=49_500.0,
            decision_uid=f"decision-{assessment.assessment_id}",
        )
        decision = CTOAiDecision(
            decision_uid=directive.decision_uid or "decision-runtime-contract-1",
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

        return RuntimeContractEvent(
            event_id="decided",
            trace_id=event.trace_id,
            parent_id=event.event_id,
            payload=decision,
        )


class RuntimeContractExecutionEngine:
    def execute(self, event: RuntimeContractEvent) -> RuntimeContractEvent:
        decision = cast(CTOAiDecision, event.payload)
        report = ExecutionReport(
            directive_id=decision.directive_id,
            symbol=decision.symbol,
            action=decision.action,
            status=ExecutionStatus.SUBMITTED,
            quantity=decision.size,
            avg_price=decision.directive.price,
            fees_paid=0.0,
            reported_at=FIXED_NOW,
            notes=[
                "runtime contract execution result",
                f"decision_uid={decision.decision_uid}",
                f"trace_id={event.trace_id}",
            ],
        )

        return RuntimeContractEvent(
            event_id="executed",
            trace_id=event.trace_id,
            parent_id=event.event_id,
            payload=report,
        )


def test_runtime_contract_e2e_executes_real_pipeline_synchronously():
    assert event_bus_module.EventMessage
    assert execution_engine.ExecutionEngine

    event_bus = RuntimeContractEventBus()
    risk_runtime = RuntimeContractRiskEngine()
    gate_runtime = RuntimeContractTradingGate()
    execution_runtime = RuntimeContractExecutionEngine()

    root_event = RuntimeContractEvent(
        event_id="created",
        trace_id=TRACE_ID,
        parent_id=None,
        payload=TradeHypothesis(
            hypothesis_id="hyp-runtime-contract-1",
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
            notes=["runtime contract"],
        ),
    )

    emitted = event_bus.emit(root_event)
    assessed = event_bus.emit(risk_runtime.evaluate(emitted))
    decided = event_bus.emit(gate_runtime.decide(assessed))
    executed = event_bus.emit(execution_runtime.execute(decided))

    decision = cast(CTOAiDecision, decided.payload)
    result = cast(ExecutionReport, executed.payload)

    assert decision is not None
    assert result is not None
    assert result.status is ExecutionStatus.SUBMITTED
    assert result.directive_id == decision.directive_id
    assert [event.trace_id for event in event_bus.events] == [TRACE_ID] * 4
    assert [event.parent_id for event in event_bus.events] == [
        None,
        "created",
        "risk-checked",
        "decided",
    ]
    assert replace(executed, payload=result).trace_id == decision.meta["trace_id"]
