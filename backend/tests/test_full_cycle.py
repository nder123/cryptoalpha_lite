# Ensure the backend package is importable when tests run without installation.
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = str(BACKEND_ROOT)
if BACKEND_PATH not in sys.path:  # pragma: no cover
    sys.path.insert(0, BACKEND_PATH)

from app.core.config import get_settings
from app.core.runtime_config import RuntimeConfigManager
from app.domain import streams
from app.domain.events import (
    ExecutionReport,
    ExecutionStatus,
    HypothesisType,
    MarketSnapshot,
    MarketStatus,
    PositionEventType,
    RiskAssessment,
    RiskDecision,
    SymbolCategory,
    TradeAction,
    TradeDirective,
    TradeHypothesis,
)
from app.infrastructure.event_bus import EventMessage
from app.services.position_manager import PositionManager
from app.services.rl_state_builder import STATE_KEY_PREFIX, RLStateBuilder
from app.services.trade_stats_recorder import TradeStatsRecorder
from app.state.cto_ai import CTOAIOrchestrator
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState


class FakeEventBus:
    def __init__(self) -> None:
        self.published: Dict[str, List[Any]] = defaultdict(list)
        self.acks: List[tuple[str, str, str]] = []
        self._counter = 0

    async def publish(self, stream: str, event: Any, *, id: str | None = None) -> str:
        self._counter += 1
        message_id = (
            id
            or f"{int(datetime.now(timezone.utc).timestamp() * 1000)}-{self._counter}"
        )
        self.published[stream].append(event)
        return message_id

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        self.acks.append((stream, group, message_id))


class FakeBroadcastManager(BroadcastManager):
    def __init__(self) -> None:
        super().__init__()
        self.messages: List[dict[str, Any]] = []

    async def broadcast(self, payload: dict[str, Any]) -> None:
        self.messages.append(payload)


class FakeRedis:
    def __init__(self) -> None:
        self.storage: Dict[str, Any] = {}

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        self.storage[key] = value


@dataclass
class _Session:
    session_id: str
    symbol: str
    direction: str
    mode: str
    opened_at: datetime
    entry_directive_id: str
    entry_price: Optional[Decimal]
    entry_qty: Optional[Decimal]
    target_price: Optional[Decimal]
    stop_price: Optional[Decimal]
    comment: Optional[str]
    closed_at: Optional[datetime] = None
    exit_directive_id: Optional[str] = None
    exit_price: Optional[Decimal] = None
    exit_qty: Optional[Decimal] = None
    pnl_usdt: Optional[Decimal] = None
    pnl_pct: Optional[Decimal] = None
    tp_hit: bool = False
    sl_hit: bool = False
    duration_seconds: Optional[int] = None
    risk_reward_ratio: Optional[Decimal] = None
    updated_at: Optional[datetime] = None


class InMemoryTradeStatsRepository:
    def __init__(self) -> None:
        self.sessions: Dict[str, _Session] = {}
        self.fills: List[dict[str, Any]] = []
        self.hypothesis_sessions: Dict[str, dict[str, Any]] = {}

    async def create_session(self, data) -> None:  # pragma: no cover - simple storage
        self.sessions[data.session_id] = _Session(
            session_id=data.session_id,
            symbol=data.symbol,
            direction=data.direction,
            mode=data.mode,
            opened_at=data.opened_at,
            entry_directive_id=data.entry_directive_id,
            entry_price=data.entry_price,
            entry_qty=data.entry_qty,
            target_price=data.target_price,
            stop_price=data.stop_price,
            comment=data.comment,
        )

    async def create_hypothesis_session(
        self,
        *,
        hypothesis_id: str,
        session_id: str,
        symbol: str,
        direction: str,
        opened_at: datetime,
    ) -> None:  # pragma: no cover - simple storage
        self.hypothesis_sessions[session_id] = {
            "hypothesis_id": hypothesis_id,
            "symbol": symbol,
            "direction": direction,
            "opened_at": opened_at,
            "closed_at": None,
            "pnl_usdt": None,
            "pnl_pct": None,
        }

    async def add_fill(self, data) -> None:  # pragma: no cover - simple storage
        self.fills.append(
            {
                "session_id": data.session_id,
                "directive_id": data.directive_id,
                "order_id": data.order_id,
                "side": data.side,
                "price": data.price,
                "quantity": data.quantity,
                "fees": data.fees,
                "reported_at": data.reported_at,
            }
        )

    async def get_open_session(self, symbol: str, direction: str) -> Optional[_Session]:
        for session in self.sessions.values():
            if (
                session.symbol == symbol
                and session.direction == direction
                and session.closed_at is None
            ):
                return session
        return None

    async def close_session(self, data) -> None:  # pragma: no cover - simple storage
        session = self.sessions.get(data.session_id)
        if session is None:
            return
        session.closed_at = data.closed_at
        session.exit_directive_id = data.exit_directive_id
        session.exit_price = data.exit_price
        session.exit_qty = data.exit_qty
        session.pnl_usdt = data.pnl_usdt
        session.pnl_pct = data.pnl_pct
        session.tp_hit = data.tp_hit
        session.sl_hit = data.sl_hit
        session.duration_seconds = data.duration_seconds
        session.risk_reward_ratio = data.risk_reward_ratio
        session.comment = data.comment
        session.updated_at = datetime.now(timezone.utc)
        await self.update_hypothesis_session_on_close(
            session_id=data.session_id,
            closed_at=data.closed_at,
            pnl_usdt=data.pnl_usdt,
            pnl_pct=data.pnl_pct,
        )

    async def list_sessions(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        items: List[dict[str, Any]] = []
        for session in self.sessions.values():
            if symbol and session.symbol != symbol:
                continue
            if start and session.opened_at < start:
                continue
            if end and session.opened_at > end:
                continue
            items.append(
                {
                    "session_id": session.session_id,
                    "symbol": session.symbol,
                    "direction": session.direction,
                    "mode": session.mode,
                    "opened_at": session.opened_at.isoformat(),
                    "closed_at": (
                        session.closed_at.isoformat() if session.closed_at else None
                    ),
                    "entry_price": (
                        float(session.entry_price)
                        if session.entry_price is not None
                        else None
                    ),
                    "entry_qty": (
                        float(session.entry_qty)
                        if session.entry_qty is not None
                        else None
                    ),
                    "exit_price": (
                        float(session.exit_price)
                        if session.exit_price is not None
                        else None
                    ),
                    "exit_qty": (
                        float(session.exit_qty)
                        if session.exit_qty is not None
                        else None
                    ),
                    "target_price": (
                        float(session.target_price)
                        if session.target_price is not None
                        else None
                    ),
                    "stop_price": (
                        float(session.stop_price)
                        if session.stop_price is not None
                        else None
                    ),
                    "pnl_usdt": (
                        float(session.pnl_usdt)
                        if session.pnl_usdt is not None
                        else None
                    ),
                    "pnl_pct": (
                        float(session.pnl_pct) if session.pnl_pct is not None else None
                    ),
                    "tp_hit": session.tp_hit,
                    "sl_hit": session.sl_hit,
                    "duration_seconds": session.duration_seconds,
                    "risk_reward_ratio": (
                        float(session.risk_reward_ratio)
                        if session.risk_reward_ratio is not None
                        else None
                    ),
                    "entry_directive_id": session.entry_directive_id,
                    "exit_directive_id": session.exit_directive_id,
                    "comment": session.comment,
                }
            )
        items.sort(key=lambda item: item["opened_at"] or "", reverse=True)
        return {"items": items[:limit], "total": len(items)}

    async def update_hypothesis_session_on_close(
        self,
        *,
        session_id: str,
        closed_at: datetime,
        pnl_usdt: Optional[Decimal],
        pnl_pct: Optional[Decimal],
    ) -> None:  # pragma: no cover - simple storage
        entry = self.hypothesis_sessions.get(session_id)
        if entry is None:
            return
        entry.update(
            {
                "closed_at": closed_at,
                "pnl_usdt": pnl_usdt,
                "pnl_pct": pnl_pct,
            }
        )

    async def list_hypothesis_stats(self, *, limit: int = 100) -> List[dict[str, Any]]:
        grouped: Dict[str, dict[str, Any]] = {}
        for session in self.hypothesis_sessions.values():
            hypothesis_id = session["hypothesis_id"]
            stats = grouped.setdefault(
                hypothesis_id,
                {
                    "hypothesis_id": hypothesis_id,
                    "symbol": session.get("symbol"),
                    "direction": session.get("direction"),
                    "trades": 0,
                    "total_pnl_usdt": Decimal("0"),
                    "total_pct": Decimal("0"),
                    "count_pct": 0,
                    "last_closed_at": None,
                },
            )
            stats["trades"] += 1
            pnl_usdt = session.get("pnl_usdt")
            if pnl_usdt is not None:
                stats["total_pnl_usdt"] += Decimal(pnl_usdt)
            pnl_pct = session.get("pnl_pct")
            if pnl_pct is not None:
                stats["total_pct"] += Decimal(pnl_pct)
                stats["count_pct"] += 1
            closed_at = session.get("closed_at")
            if closed_at is not None and (
                stats["last_closed_at"] is None or closed_at > stats["last_closed_at"]
            ):
                stats["last_closed_at"] = closed_at

        rows: List[dict[str, Any]] = []
        for payload in grouped.values():
            count_pct = payload.pop("count_pct")
            total_pct = payload.pop("total_pct")
            payload["total_pnl_usdt"] = (
                float(payload["total_pnl_usdt"])
                if payload["total_pnl_usdt"] is not None
                else None
            )
            payload["avg_pnl_pct"] = float(total_pct / count_pct) if count_pct else None
            payload["last_closed_at"] = (
                payload["last_closed_at"].isoformat()
                if payload["last_closed_at"]
                else None
            )
            rows.append(payload)

        rows.sort(key=lambda item: item.get("total_pnl_usdt") or 0.0, reverse=True)
        return rows[:limit]


@pytest.mark.asyncio
async def test_full_trade_cycle_updates_stats_and_rl_state() -> None:
    settings = get_settings()
    config_manager = RuntimeConfigManager(settings)
    store = GlobalAppState()
    await store.set_runtime_config(await config_manager.get_config())

    bus = FakeEventBus()
    notifier = FakeBroadcastManager()
    orchestrator = CTOAIOrchestrator(config_manager, store)
    stats_repo = InMemoryTradeStatsRepository()
    trade_stats_recorder = TradeStatsRecorder(bus, stats_repo)
    fake_redis = FakeRedis()
    rl_builder = RLStateBuilder(bus, fake_redis, config_manager, stats_repo)
    position_manager = PositionManager(
        bus, orchestrator, store, notifier, config_manager
    )

    now = datetime.now(timezone.utc)
    symbol = "BTCUSDT"

    market_snapshot = MarketSnapshot(
        symbol=symbol,
        timestamp=now,
        market_score=0.75,
        status=MarketStatus.NEUTRAL,
        category=SymbolCategory.CANDIDATE,
    )
    await store.update_market(market_snapshot)

    hypothesis = TradeHypothesis(
        hypothesis_id="hyp-1",
        symbol=symbol,
        created_at=now,
        hypothesis_type=HypothesisType.MEAN_REVERSION,
        confidence=0.82,
        direction="long",
        entry_price=31000.0,
        target_price=31620.0,
        stop_price=30380.0,
        position_size=0.1,
        leverage=2.0,
        notional_usdt=3100.0,
    )

    assessment = RiskAssessment(
        assessment_id="risk-1",
        hypothesis_id=hypothesis.hypothesis_id,
        symbol=symbol,
        evaluated_at=now + timedelta(seconds=5),
        decision=RiskDecision.APPROVED,
        blockers=[],
        risk_metrics={"confidence_delta": 0.05},
    )

    await orchestrator.handle_hypothesis(hypothesis)
    directive = await orchestrator.handle_risk_assessment(assessment)
    assert directive is not None and directive.action.value == "open"
    await store.upsert_directive(directive)

    event_hypothesis = EventMessage("1-1", streams.RESEARCH_HYPOTHESES, hypothesis)
    event_risk = EventMessage("1-2", streams.RISK_ASSESSMENTS, assessment)
    event_directive = EventMessage("1-3", streams.CTOAI_DIRECTIVES, directive)
    await rl_builder._handle_hypothesis(event_hypothesis)
    await rl_builder._handle_risk(event_risk)
    await rl_builder._handle_directive(event_directive)

    trade_stats_recorder._remember_directive(directive)
    position_manager._directive_cache[directive.directive_id] = directive

    open_report = ExecutionReport(
        directive_id=directive.directive_id,
        symbol=symbol,
        action=TradeAction.OPEN,
        status=ExecutionStatus.FILLED,
        quantity=directive.quantity,
        avg_price=directive.price,
        fees_paid=0.4,
        reported_at=now + timedelta(seconds=30),
        notes=["dry-run fill", "decision_uid=dec-1"],
    )

    await position_manager._register_open_fill(directive, open_report)
    await rl_builder._handle_execution(
        EventMessage("1-4", streams.EXECUTION_REPORTS, open_report)
    )
    await trade_stats_recorder._handle_execution(open_report)

    tracker = position_manager._positions[directive.directive_id]
    config = await config_manager.get_config()
    await position_manager._dispatch_close(
        tracker, tracker.entry_price, "timeout", config
    )

    close_directive = bus.published[streams.CTOAI_DIRECTIVES][-1]
    assert isinstance(close_directive, TradeDirective)
    position_manager._directive_cache[close_directive.directive_id] = close_directive
    trade_stats_recorder._remember_directive(close_directive)

    close_report = ExecutionReport(
        directive_id=close_directive.directive_id,
        symbol=symbol,
        action=TradeAction.CLOSE,
        status=ExecutionStatus.FILLED,
        quantity=close_directive.quantity,
        avg_price=close_directive.price,
        fees_paid=0.4,
        reported_at=now + timedelta(seconds=90),
        notes=["dry-run close", "decision_uid=dec-1"],
    )

    await position_manager._register_close_update(close_directive, close_report)
    await rl_builder._handle_directive(
        EventMessage("1-5", streams.CTOAI_DIRECTIVES, close_directive)
    )
    await rl_builder._handle_execution(
        EventMessage("1-6", streams.EXECUTION_REPORTS, close_report)
    )
    await trade_stats_recorder._handle_execution(close_report)

    await rl_builder._update_portfolio(symbol)

    session = stats_repo.sessions[directive.directive_id]
    assert session.closed_at is not None
    assert len(stats_repo.fills) == 2

    position_events = bus.published[streams.POSITION_EVENTS]
    event_types = {event.event for event in position_events}
    assert PositionEventType.OPEN_TRACKED in event_types
    assert PositionEventType.CLOSE_CONFIRMED in event_types

    state = rl_builder._states[symbol]
    assert state.portfolio.get("trades_count") == 1
    cache_key = f"{STATE_KEY_PREFIX}:{symbol}"
    assert cache_key in fake_redis.storage
