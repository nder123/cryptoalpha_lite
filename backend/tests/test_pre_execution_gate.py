from __future__ import annotations

from datetime import datetime, timezone

from app.domain.events import CTOAiDecision, TradeAction, TradeDirective, TradingMode
from app.services.pre_execution_gate import (
    is_execution_allowed,
    validate_before_execution,
)

FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _directive(*, action: TradeAction = TradeAction.OPEN) -> TradeDirective:
    return TradeDirective(
        directive_id="directive-pre-exec-1",
        hypothesis_id="hyp-pre-exec-1",
        symbol="BTCUSDT",
        issued_at=FIXED_NOW,
        action=action,
        rationale=["pre-execution gate test"],
        mode=TradingMode.MANUAL,
        confidence=0.8,
        direction="long",
        order_type="limit",
        quantity=0.001,
        price=50_000.0,
        leverage=1.0,
        notional_usdt=50.0,
        decision_uid="decision-pre-exec-1",
    )


def _decision(
    *,
    action: TradeAction = TradeAction.OPEN,
    trace_id: str | None = "trace-pre-exec-1",
    risk_assessment_id: str | None = "risk-pre-exec-1",
    directive: TradeDirective | None = None,
) -> CTOAiDecision:
    decision_directive = directive or _directive(action=action)
    meta: dict[str, str] = {}
    if trace_id is not None:
        meta["trace_id"] = trace_id
    if risk_assessment_id is not None:
        meta["risk_assessment_id"] = risk_assessment_id

    return CTOAiDecision(
        decision_uid="decision-pre-exec-1",
        directive_id=decision_directive.directive_id,
        symbol=decision_directive.symbol,
        issued_at=decision_directive.issued_at,
        action=action,
        size=decision_directive.quantity,
        notional_usdt=decision_directive.notional_usdt,
        source="fsm",
        meta=meta,
        directive=decision_directive,
    )


def test_pre_execution_gate_allows_valid_decision():
    decision = _decision()

    result = validate_before_execution(decision)

    assert result.ok
    assert result.violations == ()
    assert is_execution_allowed(decision)


def test_pre_execution_gate_rejects_missing_trace_id():
    decision = _decision(trace_id=None)

    result = validate_before_execution(decision)

    assert not result.ok
    assert not is_execution_allowed(decision)
    assert any(violation.code == "TRACE_ID_MISSING" for violation in result.violations)


def test_pre_execution_gate_rejects_missing_risk_origin():
    decision = _decision(risk_assessment_id=None)

    result = validate_before_execution(decision)

    assert not result.ok
    assert any(
        violation.code == "DECISION_WITHOUT_RISK" for violation in result.violations
    )


def test_pre_execution_gate_rejects_directive_origin_mismatch():
    mismatched = _directive().model_copy(update={"decision_uid": "other-decision"})
    decision = _decision(directive=mismatched)

    result = validate_before_execution(decision)

    assert not result.ok
    assert any(
        violation.code == "DECISION_ORIGIN_INVALID" for violation in result.violations
    )


def test_pre_execution_gate_rejects_denied_decision_without_side_effects():
    decision = _decision(
        action=TradeAction.REJECT, directive=_directive(action=TradeAction.REJECT)
    )
    before_meta = dict(decision.meta)

    result = validate_before_execution(decision)

    assert not result.ok
    assert not is_execution_allowed(decision)
    assert decision.meta == before_meta
    assert any(
        violation.code == "DECISION_NOT_EXECUTABLE" for violation in result.violations
    )
