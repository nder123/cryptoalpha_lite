"""Autopilot that generates OPEN->CLOSE cycles for RL training in dry-run.

This service is intended for unattended warm-up runs: it periodically issues manual-style
trade directives to generate closed trade sessions, which can then be converted into RL
experience.

Safety constraints:
- Only operates when runtime config has dry_run=true and rl_autopilot_enabled=true.
- Issues at most one open position at a time (per configured symbol + direction).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.domain import streams
from app.domain.events import CTOAiDecision, TradeAction, TradeDirective, TradingMode
from app.infrastructure.database import db_session
from app.infrastructure.event_bus import EventBus
from app.repositories.models import TradeSession
from app.repositories.trade_stats import TradeStatsRepository
from app.state.cto_ai import CTOAIOrchestrator
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState


class RLAutopilot:
    def __init__(
        self,
        bus: EventBus,
        config_manager: RuntimeConfigManager,
        trade_stats_repo: TradeStatsRepository,
        orchestrator: CTOAIOrchestrator,
        store: GlobalAppState,
        notifier: BroadcastManager,
    ) -> None:
        self._logger = get_logger(__name__)
        self._bus = bus
        self._config_manager = config_manager
        self._repo = trade_stats_repo
        self._orchestrator = orchestrator
        self._store = store
        self._notifier = notifier
        self._last_cycle_at: datetime | None = None
        self._last_direction: str | None = None
        self._last_close_requested_at: dict[str, datetime] = {}

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            config = await self._config_manager.get_config()
            if not config.dry_run or not getattr(config, "rl_autopilot_enabled", False):
                await self._sleep(stop_event, 5.0)
                continue

            symbol = str(
                getattr(config, "rl_autopilot_symbol", "BTCUSDT") or "BTCUSDT"
            ).upper()
            hold_seconds = float(
                getattr(config, "rl_autopilot_hold_seconds", 60.0) or 60.0
            )
            interval_seconds = float(
                getattr(config, "rl_autopilot_interval_seconds", 300.0) or 300.0
            )

            open_session = await self._get_open_session_for_symbol(symbol)

            if open_session is not None:
                opened_at = open_session.opened_at
                if opened_at is None:
                    await self._sleep(stop_event, 2.0)
                    continue
                if opened_at.tzinfo is None:
                    opened_at = opened_at.replace(tzinfo=timezone.utc)

                age = (datetime.now(timezone.utc) - opened_at).total_seconds()
                if age >= hold_seconds:
                    if await self._execution_engine_ok():
                        now = datetime.now(timezone.utc)
                        session_key = str(getattr(open_session, "session_id", "") or "")
                        last_close = (
                            self._last_close_requested_at.get(session_key)
                            if session_key
                            else None
                        )
                        if (
                            last_close is None
                            or (now - last_close).total_seconds() >= 15.0
                        ):
                            await self._issue_close(
                                symbol=symbol,
                                direction=open_session.direction,
                                config=config,
                            )
                            if session_key:
                                self._last_close_requested_at[session_key] = now
                await self._sleep(stop_event, 2.0)
                continue

            # No open session: we can drop stale close markers to keep memory bounded.
            if self._last_close_requested_at:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
                self._last_close_requested_at = {
                    key: value
                    for key, value in self._last_close_requested_at.items()
                    if value >= cutoff
                }

            direction = self._pick_direction(
                str(
                    getattr(config, "rl_autopilot_direction", "alternate")
                    or "alternate"
                )
            )

            now = datetime.now(timezone.utc)
            if self._last_cycle_at is not None:
                elapsed = (now - self._last_cycle_at).total_seconds()
                if elapsed < interval_seconds:
                    await self._sleep(
                        stop_event, min(5.0, max(1.0, interval_seconds - elapsed))
                    )
                    continue

            if not await self._execution_engine_ok():
                await self._sleep(stop_event, 5.0)
                continue

            if not await self._within_anti_ruin_limits(config):
                await self._sleep(stop_event, 10.0)
                continue

            await self._issue_open(symbol=symbol, direction=direction, config=config)
            self._last_cycle_at = now
            await self._sleep(stop_event, 2.0)

    @staticmethod
    async def _get_open_session_for_symbol(symbol: str) -> TradeSession | None:
        stmt = (
            select(TradeSession)
            .where(
                TradeSession.symbol == symbol,
                TradeSession.closed_at.is_(None),
            )
            .order_by(TradeSession.opened_at.desc())
            .limit(1)
        )
        async with db_session() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _within_anti_ruin_limits(self, config: object) -> bool:
        max_trades_per_day = int(getattr(config, "max_trades_per_day", 0) or 0)
        max_daily_loss_usdt = float(getattr(config, "max_daily_loss_usdt", 0.0) or 0.0)
        max_consecutive_losses = int(getattr(config, "max_consecutive_losses", 0) or 0)

        if (
            max_trades_per_day <= 0
            and max_daily_loss_usdt <= 0
            and max_consecutive_losses <= 0
        ):
            return True

        stats = await self._compute_daily_limits(max(200, max_consecutive_losses + 5))
        trades_today = float(stats.get("trades_today") or 0.0)
        pnl_today = float(stats.get("pnl_today") or 0.0)
        consecutive_losses = int(float(stats.get("consecutive_losses") or 0.0))

        if max_trades_per_day > 0 and trades_today >= float(max_trades_per_day):
            self._logger.warning(
                "rl_autopilot_blocked_max_trades",
                trades_today=trades_today,
                max_trades_per_day=max_trades_per_day,
            )
            return False

        if max_daily_loss_usdt > 0 and pnl_today <= -abs(max_daily_loss_usdt):
            self._logger.warning(
                "rl_autopilot_blocked_daily_loss",
                pnl_today=pnl_today,
                max_daily_loss_usdt=max_daily_loss_usdt,
            )
            return False

        if max_consecutive_losses > 0 and consecutive_losses >= max_consecutive_losses:
            self._logger.warning(
                "rl_autopilot_blocked_consecutive_losses",
                consecutive_losses=consecutive_losses,
                max_consecutive_losses=max_consecutive_losses,
            )
            return False

        return True

    async def _compute_daily_limits(self, recent_limit: int) -> dict[str, float]:
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
                    .limit(max(1, int(recent_limit)))
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

    async def _execution_engine_ok(self) -> bool:
        try:
            health = await self._store.get_service_health()
        except Exception:
            return True
        payload = health.get("execution-engine") or {}
        status = str(payload.get("status") or "unknown").lower()
        return status == "healthy"

    def _pick_direction(self, mode: str) -> str:
        normalized = (mode or "alternate").lower()
        if normalized in {"long", "short"}:
            self._last_direction = normalized
            return normalized
        if self._last_direction == "long":
            self._last_direction = "short"
        else:
            self._last_direction = "long"
        return self._last_direction

    async def _issue_open(self, *, symbol: str, direction: str, config: object) -> None:
        quantity = float(getattr(config, "rl_autopilot_quantity", 0.001) or 0.001)
        leverage = float(getattr(config, "rl_autopilot_leverage", 1.0) or 1.0)

        now = datetime.now(timezone.utc)
        directive = TradeDirective(
            directive_id=f"auto-{uuid4().hex}",
            hypothesis_id=None,
            symbol=symbol,
            issued_at=now,
            action=TradeAction.OPEN,
            rationale=["RL autopilot"],
            mode=TradingMode.MANUAL,
            confidence=1.0,
            direction=direction,
            order_type="market",
            quantity=quantity,
            price=None,
            leverage=leverage,
            reduce_only=False,
            notional_usdt=0.0,
            expires_at=now + timedelta(minutes=5),
            take_profit_price=None,
            stop_loss_price=None,
        )

        decision: CTOAiDecision = self._orchestrator.build_decision(
            directive,
            source="operator",
            meta={"reason": "rl_autopilot"},
        )
        await self._store.upsert_directive(directive)
        await self._bus.publish(streams.CTOAI_DIRECTIVES, directive)
        await self._bus.publish(streams.CTOAI_DECISIONS, decision)
        await self._notifier.broadcast(await self._store.build_dashboard_state())
        self._logger.info(
            "rl_autopilot_open_issued",
            directive_id=directive.directive_id,
            symbol=symbol,
            direction=direction,
        )

    async def _issue_close(
        self, *, symbol: str, direction: str, config: object
    ) -> None:
        quantity = float(getattr(config, "rl_autopilot_quantity", 0.001) or 0.001)
        leverage = float(getattr(config, "rl_autopilot_leverage", 1.0) or 1.0)

        now = datetime.now(timezone.utc)
        directive = TradeDirective(
            directive_id=f"auto-{uuid4().hex}",
            hypothesis_id=None,
            symbol=symbol,
            issued_at=now,
            action=TradeAction.CLOSE,
            rationale=["RL autopilot"],
            mode=TradingMode.MANUAL,
            confidence=1.0,
            direction=direction,
            order_type="market",
            quantity=quantity,
            price=None,
            leverage=leverage,
            reduce_only=True,
            notional_usdt=0.0,
            expires_at=now + timedelta(minutes=5),
            take_profit_price=None,
            stop_loss_price=None,
        )

        decision: CTOAiDecision = self._orchestrator.build_decision(
            directive,
            source="operator",
            meta={"reason": "rl_autopilot"},
        )
        await self._store.upsert_directive(directive)
        await self._bus.publish(streams.CTOAI_DIRECTIVES, directive)
        await self._bus.publish(streams.CTOAI_DECISIONS, decision)
        await self._notifier.broadcast(await self._store.build_dashboard_state())
        self._logger.info(
            "rl_autopilot_close_issued",
            directive_id=directive.directive_id,
            symbol=symbol,
            direction=direction,
        )

    @staticmethod
    async def _sleep(stop_event: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(0.1, seconds))
        except asyncio.TimeoutError:
            return


async def run_rl_autopilot(
    stop_event: asyncio.Event,
    bus: EventBus,
    config_manager: RuntimeConfigManager,
    trade_stats_repo: TradeStatsRepository,
    orchestrator: CTOAIOrchestrator,
    store: GlobalAppState,
    notifier: BroadcastManager,
) -> None:
    service = RLAutopilot(
        bus, config_manager, trade_stats_repo, orchestrator, store, notifier
    )
    await service.run(stop_event)
