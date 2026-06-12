from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import cast

from pydantic import BaseModel

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
TRACE_ID = "trace-runtime-contract-determinism"


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    trace_id: str
    parent_id: str | None
    payload: object


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
            safe_mode_active=False,
            coherence_break_count=0,
            since=FIXED_NOW.isoformat(),
            reasons=[],
        )


@dataclass(frozen=True)
class GateOutput:
    gate: trading_gate.GateDecision
    decision: CTOAiDecision


class RuntimeTradingGate:
    def decide(self, event: RuntimeEvent) -> RuntimeEvent:
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
            decision_uid=directive.decision_uid or "decision-runtime-contract",
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
            payload=GateOutput(gate=gate_decision, decision=decision),
        )


class RuntimeExecutionEngine:
    def execute(self, event: RuntimeEvent) -> RuntimeEvent:
        output = cast(GateOutput, event.payload)
        decision = output.decision
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

        return RuntimeEvent(
            event_id="executed",
            trace_id=event.trace_id,
            parent_id=event.event_id,
            payload=report,
        )


def _synthetic_input() -> RuntimeEvent:
    return RuntimeEvent(
        event_id="created",
        trace_id=TRACE_ID,
        parent_id=None,
        payload=TradeHypothesis(
            hypothesis_id="hyp-runtime-contract-determinism",
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
            notes=["runtime contract determinism"],
        ),
    )


def _run_runtime_contract() -> tuple[list[RuntimeEvent], list[dict[str, object]]]:
    event_bus = RuntimeEventBus()
    risk_runtime = RuntimeRiskEngine()
    gate_runtime = RuntimeTradingGate()
    execution_runtime = RuntimeExecutionEngine()

    emitted = event_bus.emit(_synthetic_input())
    assessed = event_bus.emit(risk_runtime.evaluate(emitted))
    decided = event_bus.emit(gate_runtime.decide(assessed))
    executed = event_bus.emit(execution_runtime.execute(decided))

    return event_bus.events, [
        {"stage": "risk_decision", "payload": assessed.payload},
        {"stage": "gate_decision", "payload": decided.payload},
        {"stage": "execution_result", "payload": executed.payload},
    ]


def _to_plain(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    return value


def _normalize_timestamps(value: object) -> object:
    value = _to_plain(value)
    if isinstance(value, datetime):
        return "<timestamp>"
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _normalize_timestamps(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_timestamps(item) for item in value]
    return value


def _serialize_trace(trace: list[dict[str, object]]) -> str:
    normalized = _normalize_timestamps(trace)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def test_runtime_contract_outputs_are_deterministic_after_timestamp_normalization():
    assert risk_engine.RiskEngine
    assert trading_gate.GateDecision
    assert execution_engine.ExecutionEngine

    events_1, trace_1 = _run_runtime_contract()
    events_2, trace_2 = _run_runtime_contract()

    assert [event.trace_id for event in events_1] == [TRACE_ID] * 4
    assert [event.trace_id for event in events_2] == [TRACE_ID] * 4
    assert [event.parent_id for event in events_1] == [
        None,
        "created",
        "risk-checked",
        "decided",
    ]
    assert [event.parent_id for event in events_2] == [
        None,
        "created",
        "risk-checked",
        "decided",
    ]

    assert [item["stage"] for item in trace_1] == [
        "risk_decision",
        "gate_decision",
        "execution_result",
    ]
    assert _serialize_trace(trace_1) == _serialize_trace(trace_2)
