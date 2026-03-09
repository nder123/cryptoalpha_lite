"""Repository helper for trade statistics storage and aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import and_, case, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.infrastructure.database import db_session
from app.repositories.models import HypothesisSession, TradeFill, TradeSession


@dataclass(slots=True)
class TradeSessionDTO:
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


@dataclass(slots=True)
class TradeFillDTO:
    session_id: str
    directive_id: str
    order_id: Optional[str]
    side: Optional[str]
    price: Optional[Decimal]
    quantity: Optional[Decimal]
    fees: Optional[Decimal]
    reported_at: datetime


@dataclass(slots=True)
class TradeCloseDTO:
    session_id: str
    closed_at: datetime
    exit_directive_id: str
    exit_price: Optional[Decimal]
    exit_qty: Optional[Decimal]
    pnl_usdt: Optional[Decimal]
    pnl_pct: Optional[Decimal]
    tp_hit: bool
    sl_hit: bool
    duration_seconds: Optional[int]
    risk_reward_ratio: Optional[Decimal]
    comment: Optional[str]


def _to_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


class TradeStatsRepository:
    """Persistence utilities for trade statistics."""

    @staticmethod
    def _fees_subquery():
        return (
            select(
                TradeFill.session_id.label("session_id"),
                func.coalesce(func.sum(TradeFill.fees), 0).label("fees_usdt"),
            )
            .group_by(TradeFill.session_id)
            .subquery()
        )

    async def create_session(self, data: TradeSessionDTO) -> None:
        payload = {
            "session_id": data.session_id,
            "symbol": data.symbol,
            "direction": data.direction,
            "mode": data.mode,
            "opened_at": data.opened_at,
            "entry_directive_id": data.entry_directive_id,
            "entry_price": data.entry_price,
            "entry_qty": data.entry_qty,
            "target_price": data.target_price,
            "stop_price": data.stop_price,
            "comment": data.comment,
        }
        stmt = pg_insert(TradeSession).values(**payload).on_conflict_do_nothing(index_elements=["session_id"])
        async with db_session() as session:
            await session.execute(stmt)

    async def get_session_by_exit_directive_id(self, exit_directive_id: str) -> Optional[TradeSession]:
        stmt = select(TradeSession).where(TradeSession.exit_directive_id == exit_directive_id).limit(1)
        async with db_session() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_hypothesis_session(
        self,
        *,
        hypothesis_id: str,
        session_id: str,
        symbol: str,
        direction: str,
        opened_at: datetime,
    ) -> None:
        stmt = pg_insert(HypothesisSession).values(
            hypothesis_id=hypothesis_id,
            session_id=session_id,
            symbol=symbol,
            direction=direction,
            opened_at=opened_at,
        ).on_conflict_do_nothing(index_elements=[HypothesisSession.session_id])
        async with db_session() as session:
            await session.execute(stmt)

    async def add_fill(self, data: TradeFillDTO) -> None:
        stmt = insert(TradeFill).values(
            session_id=data.session_id,
            directive_id=data.directive_id,
            order_id=data.order_id,
            side=data.side,
            price=data.price,
            quantity=data.quantity,
            fees=data.fees,
            reported_at=data.reported_at,
        )
        async with db_session() as session:
            await session.execute(stmt)

    async def get_open_session(self, symbol: str, direction: str) -> Optional[TradeSession]:
        stmt = (
            select(TradeSession)
            .where(
                and_(
                    TradeSession.symbol == symbol,
                    TradeSession.direction == direction,
                    TradeSession.closed_at.is_(None),
                )
            )
            .order_by(TradeSession.opened_at.desc())
            .limit(1)
        )
        async with db_session() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def update_hypothesis_session_on_close(
        self,
        *,
        session_id: str,
        closed_at: datetime,
        pnl_usdt: Optional[Decimal],
        pnl_pct: Optional[Decimal],
    ) -> None:
        stmt = (
            update(HypothesisSession)
            .where(HypothesisSession.session_id == session_id)
            .values(
                closed_at=closed_at,
                pnl_usdt=pnl_usdt,
                pnl_pct=pnl_pct,
            )
        )
        async with db_session() as session:
            await session.execute(stmt)

    async def close_session(self, data: TradeCloseDTO) -> None:
        stmt = (
            update(TradeSession)
            .where(TradeSession.session_id == data.session_id)
            .values(
                closed_at=data.closed_at,
                exit_directive_id=data.exit_directive_id,
                exit_price=data.exit_price,
                exit_qty=data.exit_qty,
                pnl_usdt=data.pnl_usdt,
                pnl_pct=data.pnl_pct,
                tp_hit=data.tp_hit,
                sl_hit=data.sl_hit,
                duration_seconds=data.duration_seconds,
                risk_reward_ratio=data.risk_reward_ratio,
                comment=data.comment,
                updated_at=datetime.now(timezone.utc),
            )
        )
        async with db_session() as session:
            await session.execute(stmt)

    async def list_sessions(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters = []
        if start:
            filters.append(TradeSession.opened_at >= start)
        if end:
            filters.append(TradeSession.opened_at <= end)
        if symbol:
            filters.append(TradeSession.symbol == symbol)

        stmt = (
            select(TradeSession)
            .where(*filters)
            .order_by(TradeSession.opened_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count()).select_from(TradeSession).where(*filters)

        async with db_session() as session:
            rows = (await session.execute(stmt)).scalars().all()
            total = (await session.execute(count_stmt)).scalar_one()

        items = [
            {
                "session_id": row.session_id,
                "symbol": row.symbol,
                "direction": row.direction,
                "mode": row.mode,
                "opened_at": row.opened_at.isoformat() if row.opened_at else None,
                "closed_at": row.closed_at.isoformat() if row.closed_at else None,
                "entry_price": _to_float(row.entry_price),
                "entry_qty": _to_float(row.entry_qty),
                "exit_price": _to_float(row.exit_price),
                "exit_qty": _to_float(row.exit_qty),
                "target_price": _to_float(row.target_price),
                "stop_price": _to_float(row.stop_price),
                "pnl_usdt": _to_float(row.pnl_usdt),
                "pnl_pct": _to_float(row.pnl_pct),
                "tp_hit": row.tp_hit,
                "sl_hit": row.sl_hit,
                "duration_seconds": row.duration_seconds,
                "risk_reward_ratio": _to_float(row.risk_reward_ratio),
                "entry_directive_id": row.entry_directive_id,
                "exit_directive_id": row.exit_directive_id,
                "comment": row.comment,
            }
            for row in rows
        ]
        return {"items": items, "total": total}

    async def compute_summary(self, *, start: Optional[datetime] = None, end: Optional[datetime] = None) -> dict[str, Any]:
        filters = [
            TradeSession.closed_at.isnot(None),
            TradeSession.exit_directive_id.isnot(None),
            TradeSession.pnl_usdt.isnot(None),
        ]
        if start:
            filters.append(TradeSession.opened_at >= start)
        if end:
            filters.append(TradeSession.opened_at <= end)

        fees_sq = self._fees_subquery()
        agg_stmt = (
            select(
                func.sum(TradeSession.pnl_usdt).label("total_pnl_usdt"),
                func.coalesce(func.sum(fees_sq.c.fees_usdt), 0).label("total_fees_usdt"),
                func.sum(TradeSession.pnl_usdt - fees_sq.c.fees_usdt).label("total_pnl_usdt_net"),
                func.avg(TradeSession.pnl_pct).label("avg_pnl_pct"),
                func.count().label("total_trades"),
                func.sum(case((TradeSession.pnl_usdt > 0, 1), else_=0)).label("winning_trades"),
                func.avg(TradeSession.risk_reward_ratio).label("avg_rr"),
            )
            .select_from(TradeSession)
            .outerjoin(fees_sq, fees_sq.c.session_id == TradeSession.session_id)
            .where(*filters)
        )

        async with db_session() as session:
            row = (await session.execute(agg_stmt)).one()

        total_trades = row.total_trades or 0
        winning = row.winning_trades or 0
        win_rate = winning / total_trades if total_trades else 0.0
        return {
            "total_pnl_usdt": _to_float(row.total_pnl_usdt),
            "total_fees_usdt": _to_float(row.total_fees_usdt),
            "total_pnl_usdt_net": _to_float(row.total_pnl_usdt_net),
            "avg_pnl_pct": _to_float(row.avg_pnl_pct),
            "total_trades": total_trades,
            "winning_trades": winning,
            "win_rate": win_rate,
            "avg_rr": _to_float(row.avg_rr),
        }

    async def list_recent_closed(self, limit: int = 10) -> list[dict[str, Any]]:
        fees_sq = self._fees_subquery()
        stmt = (
            select(TradeSession, fees_sq.c.fees_usdt)
            .select_from(TradeSession)
            .outerjoin(fees_sq, fees_sq.c.session_id == TradeSession.session_id)
            .where(
                TradeSession.closed_at.isnot(None),
                TradeSession.exit_directive_id.isnot(None),
                TradeSession.pnl_usdt.isnot(None),
            )
            .order_by(TradeSession.closed_at.desc())
            .limit(limit)
        )

        async with db_session() as session:
            rows = (await session.execute(stmt)).all()

        return [
            {
                "session_id": session_row.session_id,
                "symbol": session_row.symbol,
                "direction": session_row.direction,
                "opened_at": session_row.opened_at.isoformat() if session_row.opened_at else None,
                "closed_at": session_row.closed_at.isoformat() if session_row.closed_at else None,
                "pnl_usdt": _to_float(session_row.pnl_usdt),
                "fees_usdt": float(fees_usdt or 0),
                "pnl_usdt_net": _to_float(session_row.pnl_usdt - (fees_usdt or 0)),
                "pnl_pct": _to_float(session_row.pnl_pct),
                "duration_seconds": session_row.duration_seconds,
                "entry_directive_id": session_row.entry_directive_id,
                "exit_directive_id": session_row.exit_directive_id,
            }
            for session_row, fees_usdt in rows
        ]

    async def list_worst_closed(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        fees_sq = self._fees_subquery()
        filters = [
            TradeSession.closed_at.isnot(None),
            TradeSession.exit_directive_id.isnot(None),
            TradeSession.pnl_usdt.isnot(None),
        ]
        if start:
            filters.append(TradeSession.opened_at >= start)
        if end:
            filters.append(TradeSession.opened_at <= end)
        if symbol:
            filters.append(TradeSession.symbol == symbol)

        net_expr = (TradeSession.pnl_usdt - func.coalesce(fees_sq.c.fees_usdt, 0)).label("pnl_usdt_net")
        stmt = (
            select(TradeSession, fees_sq.c.fees_usdt, net_expr)
            .select_from(TradeSession)
            .outerjoin(fees_sq, fees_sq.c.session_id == TradeSession.session_id)
            .where(*filters)
            .order_by(net_expr.asc(), TradeSession.closed_at.desc())
            .limit(limit)
        )

        async with db_session() as session:
            rows = (await session.execute(stmt)).all()

        return [
            {
                "session_id": session_row.session_id,
                "symbol": session_row.symbol,
                "direction": session_row.direction,
                "mode": session_row.mode,
                "opened_at": session_row.opened_at.isoformat() if session_row.opened_at else None,
                "closed_at": session_row.closed_at.isoformat() if session_row.closed_at else None,
                "entry_price": _to_float(session_row.entry_price),
                "exit_price": _to_float(session_row.exit_price),
                "pnl_usdt": _to_float(session_row.pnl_usdt),
                "fees_usdt": float(fees_usdt or 0),
                "pnl_usdt_net": _to_float(net_pnl_usdt),
                "pnl_pct": _to_float(session_row.pnl_pct),
                "tp_hit": session_row.tp_hit,
                "sl_hit": session_row.sl_hit,
                "duration_seconds": session_row.duration_seconds,
                "risk_reward_ratio": _to_float(session_row.risk_reward_ratio),
                "entry_directive_id": session_row.entry_directive_id,
                "exit_directive_id": session_row.exit_directive_id,
                "comment": session_row.comment,
            }
            for session_row, fees_usdt, net_pnl_usdt in rows
        ]

    async def dashboard_overview(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        recent_limit: int = 5,
    ) -> dict[str, Any]:
        summary = await self.compute_summary(start=start, end=end)
        recent = await self.list_recent_closed(limit=recent_limit)
        last_trade = recent[0] if recent else None
        return {
            "summary": summary,
            "recent": recent,
            "last_trade": last_trade,
        }

    async def list_hypothesis_stats(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        total_pnl = func.coalesce(func.sum(HypothesisSession.pnl_usdt), 0).label("total_pnl_usdt")
        avg_pct = func.avg(HypothesisSession.pnl_pct).label("avg_pnl_pct")
        last_closed = func.max(HypothesisSession.closed_at).label("last_closed_at")

        stmt = (
            select(
                HypothesisSession.hypothesis_id,
                func.min(HypothesisSession.symbol).label("symbol"),
                func.min(HypothesisSession.direction).label("direction"),
                func.count().label("trades"),
                total_pnl,
                avg_pct,
                last_closed,
            )
            .group_by(HypothesisSession.hypothesis_id)
            .order_by(last_closed.desc().nulls_last(), total_pnl.desc())
            .limit(limit)
        )

        async with db_session() as session:
            rows = (await session.execute(stmt)).all()

        return [
            {
                "hypothesis_id": row.hypothesis_id,
                "symbol": row.symbol,
                "direction": row.direction,
                "trades": row.trades,
                "total_pnl_usdt": _to_float(row.total_pnl_usdt),
                "avg_pnl_pct": _to_float(row.avg_pnl_pct),
                "last_closed_at": row.last_closed_at.isoformat() if row.last_closed_at else None,
            }
            for row in rows
        ]

    async def aggregate_period(
        self,
        granularity: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        filters = [
            TradeSession.closed_at.isnot(None),
            TradeSession.exit_directive_id.isnot(None),
            TradeSession.pnl_usdt.isnot(None),
        ]
        if start:
            filters.append(TradeSession.opened_at >= start)
        if end:
            filters.append(TradeSession.opened_at <= end)

        fees_sq = self._fees_subquery()
        period_expr = func.date_trunc(granularity, TradeSession.opened_at).label("period_start")

        period_stmt = (
            select(
                period_expr,
                func.sum(TradeSession.pnl_usdt).label("pnl_usdt"),
                func.coalesce(func.sum(fees_sq.c.fees_usdt), 0).label("fees_usdt"),
                func.sum(TradeSession.pnl_usdt - fees_sq.c.fees_usdt).label("pnl_usdt_net"),
                func.avg(TradeSession.pnl_pct).label("avg_pnl_pct"),
                func.count().label("trades"),
                func.avg(TradeSession.risk_reward_ratio).label("avg_rr"),
            )
            .select_from(TradeSession)
            .outerjoin(fees_sq, fees_sq.c.session_id == TradeSession.session_id)
            .where(*filters)
            .group_by(period_expr)
            .order_by(period_expr)
        )

        async with db_session() as session:
            rows = (await session.execute(period_stmt)).all()

        return [
            {
                "period_start": row.period_start.isoformat() if row.period_start else None,
                "pnl_usdt": _to_float(row.pnl_usdt),
                "fees_usdt": _to_float(row.fees_usdt),
                "pnl_usdt_net": _to_float(row.pnl_usdt_net),
                "avg_pnl_pct": _to_float(row.avg_pnl_pct),
                "trades": row.trades,
                "avg_rr": _to_float(row.avg_rr),
            }
            for row in rows
        ]

    async def export_sessions(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> list[list[str]]:
        data = await self.list_sessions(start=start, end=end, symbol=symbol, limit=10_000, offset=0)
        headers = [
            "session_id",
            "symbol",
            "direction",
            "mode",
            "opened_at",
            "closed_at",
            "entry_price",
            "entry_qty",
            "exit_price",
            "exit_qty",
            "target_price",
            "stop_price",
            "pnl_usdt",
            "pnl_pct",
            "risk_reward_ratio",
            "tp_hit",
            "sl_hit",
            "duration_seconds",
            "entry_directive_id",
            "exit_directive_id",
            "comment",
        ]
        rows = [headers]
        for item in data["items"]:
            rows.append([str(item.get(column, "")) for column in headers])
        return rows

    async def get_session(self, session_id: str) -> Optional[TradeSession]:
        stmt = select(TradeSession).where(TradeSession.session_id == session_id)
        async with db_session() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
