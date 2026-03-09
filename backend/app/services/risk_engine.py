"""Risk management engine that validates trade hypotheses."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfig, RuntimeConfigManager
from app.domain import streams
from app.domain.events import RiskAssessment, RiskDecision, TradeHypothesis
from app.infrastructure.database import db_session
from app.infrastructure.event_bus import EventBus
from app.repositories.models import TradeSession
from app.state.store import GlobalAppState


class RiskEngine:
    """Evaluates trade hypotheses against risk constraints."""

    def __init__(
        self, bus: EventBus, config_manager: RuntimeConfigManager, store: GlobalAppState
    ) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._bus = bus
        self._config_manager = config_manager
        self._config: RuntimeConfig = RuntimeConfig.from_settings(self._settings)
        self._store = store

    async def run(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.RESEARCH_HYPOTHESES,
            group="risk",
            event_type=TradeHypothesis,
            stop_event=stop_event,
        ):
            hypothesis = message.payload
            self._config = await self._config_manager.get_config()
            try:
                positions = await self._store.list_positions()
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("risk_positions_unavailable", error=str(exc))
                positions = []

            try:
                risk_budget = await self._store.get_risk_budget()
            except Exception as exc:  # noqa: BLE001
                self._logger.debug("risk_budget_unavailable", error=str(exc))
                risk_budget = {}

            current_exposure = sum(
                abs(float(position.get("notional_usdt") or 0.0))
                for position in positions
            )
            daily_stats = await self._compute_daily_limits()
            assessment = self._assess_hypothesis(
                hypothesis, current_exposure, risk_budget, daily_stats
            )
            await self._bus.publish(streams.RISK_ASSESSMENTS, assessment)
            await self._bus.ack(message.stream, "risk", message.message_id)
            if stop_event.is_set():
                break

    async def _compute_daily_limits(self) -> Dict[str, float]:
        """Compute daily trade counters for hard risk limits."""

        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        async with db_session() as session:
            base_filters = [
                TradeSession.closed_at.isnot(None),
                TradeSession.exit_directive_id.isnot(None),
                TradeSession.pnl_usdt.isnot(None),
                TradeSession.closed_at >= day_start,
            ]
            trades_today = (
                await session.execute(
                    select(func.count()).select_from(TradeSession).where(*base_filters)
                )
            ).scalar_one()
            pnl_today = (
                await session.execute(
                    select(func.coalesce(func.sum(TradeSession.pnl_usdt), 0)).where(
                        *base_filters
                    )
                )
            ).scalar_one()

            recent_rows = (
                await session.execute(
                    select(TradeSession.pnl_usdt)
                    .where(
                        TradeSession.closed_at.isnot(None),
                        TradeSession.exit_directive_id.isnot(None),
                        TradeSession.pnl_usdt.isnot(None),
                        TradeSession.closed_at >= day_start,
                    )
                    .order_by(TradeSession.closed_at.desc())
                    .limit(max(200, int(self._config.max_consecutive_losses or 0) + 5))
                )
            ).all()

        consecutive_losses = 0
        for (pnl,) in recent_rows:
            if pnl is None:
                continue
            if float(pnl) < 0:
                consecutive_losses += 1
                continue
            break

        return {
            "trades_today": float(trades_today or 0),
            "pnl_today": float(pnl_today or 0),
            "consecutive_losses": float(consecutive_losses),
        }

    def _assess_hypothesis(
        self,
        hypothesis: TradeHypothesis,
        current_exposure: float,
        risk_budget: Dict[str, object],
        daily_stats: Dict[str, float],
    ) -> RiskAssessment:
        blockers = []
        metrics: Dict[str, float] = {}

        denylist = {
            symbol.strip().upper()
            for symbol in (self._config.symbol_denylist or [])
            if symbol and symbol.strip()
        }
        if hypothesis.symbol.strip().upper() in denylist:
            blockers.append("symbol is denylisted")

        trades_today = self._safe_float(daily_stats.get("trades_today"))
        pnl_today = self._safe_float(daily_stats.get("pnl_today"))
        consecutive_losses = int(
            self._safe_float(daily_stats.get("consecutive_losses"))
        )

        metrics["trades_today"] = trades_today
        metrics["pnl_today"] = pnl_today
        metrics["consecutive_losses"] = float(consecutive_losses)

        if self._config.max_trades_per_day and trades_today >= float(
            self._config.max_trades_per_day
        ):
            blockers.append("exceeds max trades per day")

        if self._config.max_daily_loss_usdt and pnl_today <= -abs(
            float(self._config.max_daily_loss_usdt)
        ):
            blockers.append("exceeds daily loss limit")
            metrics["max_daily_loss_usdt"] = float(self._config.max_daily_loss_usdt)

        if self._config.max_consecutive_losses and consecutive_losses >= int(
            self._config.max_consecutive_losses
        ):
            blockers.append("exceeds max consecutive losses")
            metrics["max_consecutive_losses"] = float(
                self._config.max_consecutive_losses
            )

        if hypothesis.leverage > self._config.max_leverage:
            blockers.append("exceeds leverage limit")
            metrics["leverage"] = hypothesis.leverage

        portfolio_limit = (
            self._safe_float(risk_budget.get("portfolio_limit")) if risk_budget else 0.0
        )
        symbol_limits = (risk_budget or {}).get("symbol_limits") or {}
        symbol_key = hypothesis.symbol.upper()
        symbol_limit = (
            self._safe_float(symbol_limits.get(symbol_key)) if symbol_limits else 0.0
        )

        base_portfolio_limit = self._config.max_portfolio_exposure_usdt
        effective_portfolio_limit = (
            portfolio_limit if portfolio_limit > 0 else base_portfolio_limit
        )
        allocation_limit = (
            symbol_limit
            if symbol_limit > 0
            else effective_portfolio_limit * self._config.max_symbol_allocation_pct
        )
        metrics["notional"] = hypothesis.notional_usdt
        metrics["allocation_limit"] = allocation_limit
        if hypothesis.notional_usdt > allocation_limit:
            blockers.append("exceeds per-symbol allocation")

        if hypothesis.stop_price is None or hypothesis.stop_price <= 0:
            blockers.append("missing stop loss")

        if hypothesis.position_size <= 0:
            blockers.append("invalid position size")
            metrics["position_size"] = hypothesis.position_size

        metrics["portfolio_exposure"] = current_exposure
        limit = (
            effective_portfolio_limit
            if effective_portfolio_limit > 0
            else self._config.max_portfolio_exposure_usdt
        )
        if limit is not None and limit > 0:
            projected = current_exposure + max(0.0, hypothesis.notional_usdt or 0.0)
            metrics["exposure_limit"] = limit
            metrics["projected_exposure"] = projected
            if projected > limit:
                blockers.append("exceeds portfolio exposure limit")

        metrics["confidence"] = hypothesis.confidence
        if hypothesis.confidence < self._config.min_confidence_threshold:
            blockers.append("confidence below threshold")

        decision = RiskDecision.APPROVED if not blockers else RiskDecision.BLOCKED
        assessment = RiskAssessment(
            assessment_id=f"risk-{hypothesis.hypothesis_id}",
            hypothesis_id=hypothesis.hypothesis_id,
            symbol=hypothesis.symbol,
            evaluated_at=datetime.now(timezone.utc),
            decision=decision,
            blockers=blockers,
            risk_metrics=metrics,
        )
        return assessment

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0


async def run_risk_engine(
    stop_event: asyncio.Event,
    bus: EventBus,
    config_manager: RuntimeConfigManager,
    store: GlobalAppState,
) -> None:
    engine = RiskEngine(bus, config_manager, store)
    await engine.run(stop_event)
