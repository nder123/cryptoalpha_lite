"""CTO-AI orchestrator state machine."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Literal, Optional, Tuple
from uuid import uuid4

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.domain.events import (
    CTOAiDecision,
    ExecutionReport,
    MarketSnapshot,
    RiskAssessment,
    RiskDecision,
    TradeAction,
    TradeDirective,
    TradeHypothesis,
    TradingMode,
)
from app.services.rl_policy import RLPolicyDecision, RLPolicyEvaluator
from app.state.store import GlobalAppState


class CTOAIState(str):
    IDLE = "idle"
    SCANNING = "scanning"
    EVALUATING = "evaluating"
    AWAITING_RISK = "awaiting_risk"
    AWAITING_EXECUTION = "awaiting_execution"
    MANAGING_POSITION = "managing_position"
    EMERGENCY_STOP = "emergency_stop"


@dataclass(slots=True)
class HypothesisEnvelope:
    hypothesis: TradeHypothesis
    received_at: datetime
    risk_assessment: Optional[RiskAssessment] = None
    directive: Optional[TradeDirective] = None


class CTOAIOrchestrator:
    """Central decision authority."""

    def __init__(
        self,
        config_manager: RuntimeConfigManager | None = None,
        store: GlobalAppState | None = None,
    ) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._mode = TradingMode.MANUAL
        self._state: CTOAIState = CTOAIState.IDLE
        self._confidence: float = 0.0
        self._hypotheses: Deque[HypothesisEnvelope] = deque(maxlen=100)
        self._active_directives: dict[str, TradeDirective] = {}
        self._lock = asyncio.Lock()
        self._emergency_stop = asyncio.Event()
        self._config_manager = config_manager
        self._rl_evaluator: RLPolicyEvaluator | None = (
            RLPolicyEvaluator() if config_manager else None
        )
        self._store = store

    @property
    def mode(self) -> TradingMode:
        return self._mode

    @property
    def state(self) -> CTOAIState:
        return self._state

    @property
    def confidence(self) -> float:
        return self._confidence

    async def set_mode(self, mode: TradingMode) -> None:
        async with self._lock:
            self._logger.info("ctoai_set_mode", mode=mode)
            self._mode = mode

    async def emergency_stop(self) -> None:
        async with self._lock:
            self._logger.warning("ctoai_emergency_stop")
            self._state = CTOAIState.EMERGENCY_STOP
            self._emergency_stop.set()

    async def handle_market_snapshot(self, snapshot: MarketSnapshot) -> None:
        async with self._lock:
            self._logger.debug(
                "market_snapshot", symbol=snapshot.symbol, score=snapshot.market_score
            )
            if snapshot.category.value == "candidate":
                self._state = CTOAIState.EVALUATING
            elif snapshot.category.value == "watch":
                self._state = CTOAIState.SCANNING

    async def handle_hypothesis(
        self, hypothesis: TradeHypothesis
    ) -> Optional[TradeDirective]:
        async with self._lock:
            if self._emergency_stop.is_set():
                self._logger.warning(
                    "hypothesis_ignored_due_to_stop", symbol=hypothesis.symbol
                )
                return None
            envelope = HypothesisEnvelope(
                hypothesis=hypothesis, received_at=datetime.now(timezone.utc)
            )
            self._hypotheses.append(envelope)
            self._state = CTOAIState.AWAITING_RISK
            self._logger.info(
                "hypothesis_received", hypothesis_id=hypothesis.hypothesis_id
            )
            return None

    async def handle_risk_assessment(
        self, assessment: RiskAssessment
    ) -> Optional[TradeDirective]:
        async with self._lock:
            for envelope in self._hypotheses:
                if envelope.hypothesis.hypothesis_id == assessment.hypothesis_id:
                    envelope.risk_assessment = assessment
                    break
            else:
                self._logger.warning(
                    "risk_without_hypothesis", hypothesis_id=assessment.hypothesis_id
                )
                return None

            if assessment.decision != RiskDecision.APPROVED:
                self._confidence = max(0.0, self._confidence - 0.05)
                self._state = CTOAIState.IDLE
                self._logger.info(
                    "hypothesis_blocked",
                    hypothesis_id=assessment.hypothesis_id,
                    reasons=assessment.blockers,
                )
                return None

            hypothesis = envelope.hypothesis
            leverage = min(hypothesis.leverage, self._settings.max_leverage)
            rationale = [
                "Risk engine approved",
                f"confidence={hypothesis.confidence:.2f}",
                *(f"{key}={value}" for key, value in assessment.risk_metrics.items()),
            ]

            directive = TradeDirective(
                directive_id=f"dir-{assessment.assessment_id}",
                hypothesis_id=assessment.hypothesis_id,
                symbol=assessment.symbol,
                issued_at=datetime.now(timezone.utc),
                action=TradeAction.OPEN,
                rationale=rationale,
                mode=self._mode,
                confidence=(self._confidence * 0.6) + (hypothesis.confidence * 0.4),
                direction=hypothesis.direction,
                order_type="limit",
                quantity=hypothesis.position_size,
                price=hypothesis.entry_price,
                leverage=leverage,
                reduce_only=False,
                notional_usdt=hypothesis.notional_usdt,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                take_profit_price=hypothesis.target_price,
                stop_loss_price=hypothesis.stop_price,
            )
            directive, rl_reason = await self._maybe_apply_rl_policy(
                directive, assessment
            )
            if directive is None:
                try:
                    self._hypotheses.remove(envelope)
                except ValueError:
                    pass
                self._state = CTOAIState.IDLE
                self._logger.info(
                    "directive_rejected_by_rl",
                    hypothesis_id=assessment.hypothesis_id,
                    symbol=assessment.symbol,
                    reason=rl_reason,
                )
                return None

            envelope.directive = directive
            self._active_directives[directive.directive_id] = directive
            self._state = CTOAIState.AWAITING_EXECUTION
            self._logger.info(
                "directive_issued",
                directive_id=directive.directive_id,
                symbol=directive.symbol,
            )
            return directive

    async def handle_execution_report(self, report: ExecutionReport) -> None:
        async with self._lock:
            directive = self._active_directives.get(report.directive_id)
            if not directive:
                self._logger.warning(
                    "execution_unknown_directive", directive_id=report.directive_id
                )
                return

            if report.status.name == "FILLED":
                self._state = CTOAIState.MANAGING_POSITION
                self._confidence = min(1.0, self._confidence + 0.05)
            elif report.status.name in {"FAILED", "CANCELLED"}:
                self._state = CTOAIState.IDLE
                self._confidence = max(0.0, self._confidence - 0.1)

            self._logger.info(
                "execution_report",
                directive_id=report.directive_id,
                status=report.status.value,
            )
            self._active_directives.pop(report.directive_id, None)

    async def snapshot(self) -> dict[str, object]:
        async with self._lock:
            return {
                "mode": self._mode.value,
                "state": self._state,
                "confidence": self._confidence,
                "active_directives": list(self._active_directives.keys()),
            }

    def build_decision(
        self,
        directive: TradeDirective,
        *,
        source: Literal["fsm", "operator"],
        meta: Dict[str, Any] | None = None,
    ) -> CTOAiDecision:
        decision_uid = directive.decision_uid or f"dec-{uuid4().hex}"
        directive.decision_uid = decision_uid
        payload_meta = dict(meta or {})
        if directive.hypothesis_id and "hypothesis_id" not in payload_meta:
            payload_meta["hypothesis_id"] = directive.hypothesis_id

        return CTOAiDecision(
            decision_uid=decision_uid,
            directive_id=directive.directive_id,
            symbol=directive.symbol,
            issued_at=directive.issued_at,
            action=directive.action,
            size=directive.quantity,
            notional_usdt=directive.notional_usdt,
            source=source,
            meta=payload_meta,
            directive=directive,
        )

    async def _maybe_apply_rl_policy(
        self,
        directive: TradeDirective,
        assessment: RiskAssessment,
    ) -> Tuple[Optional[TradeDirective], Optional[str]]:
        if not self._config_manager or not self._rl_evaluator:
            return directive, None

        try:
            config = await self._config_manager.get_config()
        except Exception as exc:  # noqa: BLE001
            self._logger.exception("rl_policy_config_error", exc_info=exc)
            return directive, None

        if not config.rl_enabled:
            return directive, None

        state_payload = await self._rl_evaluator.fetch_state(directive.symbol)
        if not state_payload:
            self._logger.debug("rl_state_unavailable", symbol=directive.symbol)
            return directive, None

        vector = (
            state_payload.get("vector") if isinstance(state_payload, dict) else None
        )
        if not isinstance(vector, list):
            self._logger.debug("rl_state_invalid_vector", symbol=directive.symbol)
            return directive, None

        decision: RLPolicyDecision | None = await self._rl_evaluator.evaluate(
            vector,
            directive.action.value if hasattr(directive.action, "value") else None,
        )
        if decision is None:
            self._logger.debug("rl_policy_not_ready", symbol=directive.symbol)
            return directive, None

        if not decision.approved or decision.score < config.rl_policy_min_confidence:
            return None, decision.reason

        original_confidence = directive.confidence
        directive.confidence = max(
            0.0, min(1.0, original_confidence * decision.confidence_multiplier)
        )

        current_exposure = 0.0
        if self._store is not None:
            try:
                exposure_metrics = await self._store.get_exposure_metrics()
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("rl_exposure_metrics_unavailable", error=str(exc))
            else:
                current_exposure = float(
                    exposure_metrics.get("total_abs_exposure") or 0.0
                )

        available_exposure = max(
            0.0, config.max_portfolio_exposure_usdt - current_exposure
        )

        if directive.price and directive.price > 0:
            proposed_notional = directive.notional_usdt * decision.notional_multiplier
            adjusted_notional = min(proposed_notional, available_exposure)
            if adjusted_notional <= 0:
                self._logger.info(
                    "rl_adjustment_blocked_exposure",
                    directive_id=directive.directive_id,
                    symbol=directive.symbol,
                    proposed=proposed_notional,
                    available=available_exposure,
                )
                return None, "exposure limit"
            directive.notional_usdt = adjusted_notional
            directive.quantity = adjusted_notional / directive.price

        directive.rationale.append(decision.reason)
        if (
            decision.recommended_action
            and decision.recommended_action != directive.action.value
        ):
            directive.rationale.append(
                f"RL suggested action: {decision.recommended_action}"
            )
        self._logger.info(
            "directive_adjusted_by_rl",
            directive_id=directive.directive_id,
            symbol=directive.symbol,
            rl_policy_version=(
                self._rl_evaluator.current_policy_version()
                if self._rl_evaluator is not None
                else None
            ),
            rl_score=decision.score,
            confidence_before=original_confidence,
            confidence_after=directive.confidence,
        )
        return directive, decision.reason
