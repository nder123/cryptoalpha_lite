from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.infrastructure.database import db_session
from app.repositories.models import (
    AccountEquitySnapshot,
    AccountTransaction,
    ExchangeTrade,
)

MAX_TRANSACTION_ABS_AMOUNT = Decimal("1000")
LOGGER = get_logger(__name__)


def _to_decimal(value: float | str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def _ensure_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    try:
        raw = datetime.fromisoformat(value)
        if raw.tzinfo is None:
            raw = raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    except ValueError:
        return None


class ExchangeDataRepository:
    """Persistence helpers for Bybit exchange telemetry."""

    async def upsert_trades(self, trades: Iterable[dict]) -> int:
        if not trades:
            return 0
        unique_payloads: dict[str, dict[str, Any]] = {}
        for entry in trades:
            exec_id = entry.get("exec_id")
            if not exec_id:
                continue
            trade_time = _ensure_datetime(entry.get("trade_time"))
            if trade_time is None:
                continue
            payload = {
                "exec_id": exec_id,
                "order_id": entry.get("order_id"),
                "symbol": entry.get("symbol"),
                "side": (entry.get("side") or "").lower() or None,
                "trade_type": entry.get("exec_type") or entry.get("trade_type"),
                "price": _to_decimal(entry.get("price")),
                "quantity": _to_decimal(entry.get("quantity")),
                "fee": _to_decimal(entry.get("fee")),
                "fee_currency": entry.get("fee_currency"),
                "realized_pnl": _to_decimal(entry.get("realized_pnl")),
                "trade_time": trade_time,
                "created_at": datetime.now(timezone.utc),
            }
            if exec_id in unique_payloads:
                previous = unique_payloads[exec_id]
                LOGGER.debug(
                    "exchange_trade_duplicate_in_batch",
                    exec_id=exec_id,
                    previous_trade_time=(
                        previous["trade_time"].isoformat()
                        if previous["trade_time"]
                        else None
                    ),
                    new_trade_time=trade_time.isoformat() if trade_time else None,
                )
            unique_payloads[exec_id] = payload
        payloads = list(unique_payloads.values())
        if not payloads:
            return 0

        stmt = pg_insert(ExchangeTrade).values(payloads)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ExchangeTrade.exec_id],
            set_={
                "order_id": stmt.excluded.order_id,
                "symbol": stmt.excluded.symbol,
                "side": stmt.excluded.side,
                "trade_type": stmt.excluded.trade_type,
                "price": stmt.excluded.price,
                "quantity": stmt.excluded.quantity,
                "fee": stmt.excluded.fee,
                "fee_currency": stmt.excluded.fee_currency,
                "realized_pnl": stmt.excluded.realized_pnl,
                "trade_time": stmt.excluded.trade_time,
                "created_at": stmt.excluded.created_at,
            },
        )
        async with db_session() as session:
            await session.execute(stmt)
        return len(payloads)

    @staticmethod
    def _trade_to_dict(row: ExchangeTrade) -> dict[str, Any]:
        return {
            "exec_id": row.exec_id,
            "order_id": row.order_id,
            "symbol": row.symbol,
            "side": row.side,
            "trade_type": row.trade_type,
            "price": float(row.price) if row.price is not None else None,
            "quantity": float(row.quantity) if row.quantity is not None else None,
            "fee": float(row.fee) if row.fee is not None else None,
            "fee_currency": row.fee_currency,
            "realized_pnl": (
                float(row.realized_pnl) if row.realized_pnl is not None else None
            ),
            "trade_time": row.trade_time.isoformat() if row.trade_time else None,
        }

    @staticmethod
    def _transaction_to_dict(row: AccountTransaction) -> dict[str, Any]:
        return {
            "transaction_id": row.transaction_id,
            "reference_id": row.reference_id,
            "type": row.type,
            "sub_type": row.sub_type,
            "amount": float(row.amount) if row.amount is not None else None,
            "currency": row.currency,
            "fee": float(row.fee) if row.fee is not None else None,
            "created_time": row.created_time.isoformat() if row.created_time else None,
        }

    async def list_trades(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters: list[Any] = []
        if start:
            filters.append(ExchangeTrade.trade_time >= start)
        if end:
            filters.append(ExchangeTrade.trade_time <= end)
        if symbol:
            filters.append(ExchangeTrade.symbol == symbol)

        stmt = (
            select(ExchangeTrade)
            .order_by(ExchangeTrade.trade_time.desc())
            .limit(limit)
            .offset(offset)
        )
        if filters:
            stmt = stmt.where(*filters)

        count_stmt = select(func.count()).select_from(ExchangeTrade)
        if filters:
            count_stmt = count_stmt.where(*filters)

        async with db_session() as session:
            rows = (await session.execute(stmt)).scalars().all()
            total = (await session.execute(count_stmt)).scalar_one()

        items = [self._trade_to_dict(row) for row in rows]
        return {"items": items, "total": total}

    async def summarize_trades(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> dict[str, Any]:
        filters: list[Any] = []
        if start:
            filters.append(ExchangeTrade.trade_time >= start)
        if end:
            filters.append(ExchangeTrade.trade_time <= end)
        if symbol:
            filters.append(ExchangeTrade.symbol == symbol)

        stmt = select(
            func.count().label("count"),
            func.sum(ExchangeTrade.realized_pnl).label("realized"),
            func.sum(ExchangeTrade.fee).label("fees"),
        ).select_from(ExchangeTrade)
        if filters:
            stmt = stmt.where(*filters)

        async with db_session() as session:
            row = (await session.execute(stmt)).one()

        realized = float(row.realized or 0.0) if row.realized is not None else 0.0
        fees = float(row.fees or 0.0) if row.fees is not None else 0.0
        count = int(row.count or 0)

        return {
            "realized_pnl": realized,
            "fees": fees,
            "count": count,
        }

    async def list_transactions(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters: list[Any] = []
        if start:
            filters.append(AccountTransaction.created_time >= start)
        if end:
            filters.append(AccountTransaction.created_time <= end)
        if tx_type:
            filters.append(AccountTransaction.type == tx_type)

        stmt = (
            select(AccountTransaction)
            .order_by(AccountTransaction.created_time.desc())
            .limit(limit)
            .offset(offset)
        )
        if filters:
            stmt = stmt.where(*filters)

        count_stmt = select(func.count()).select_from(AccountTransaction)
        if filters:
            count_stmt = count_stmt.where(*filters)

        async with db_session() as session:
            rows = (await session.execute(stmt)).scalars().all()
            total = (await session.execute(count_stmt)).scalar_one()

        items = [self._transaction_to_dict(row) for row in rows]
        return {"items": items, "total": total}

    async def summarize_transactions(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        tx_type: Optional[str] = None,
    ) -> dict[str, Any]:
        filters: list[Any] = []
        if start:
            filters.append(AccountTransaction.created_time >= start)
        if end:
            filters.append(AccountTransaction.created_time <= end)
        if tx_type:
            filters.append(AccountTransaction.type == tx_type)

        stmt = select(
            func.count().label("count"),
            func.sum(AccountTransaction.amount).label("amount"),
            func.sum(AccountTransaction.fee).label("fees"),
        ).select_from(AccountTransaction)
        if filters:
            stmt = stmt.where(*filters)

        async with db_session() as session:
            row = (await session.execute(stmt)).one()

        amount = float(row.amount or 0.0) if row.amount is not None else 0.0
        fees = float(row.fees or 0.0) if row.fees is not None else 0.0
        count = int(row.count or 0)

        return {
            "amount": amount,
            "fees": fees,
            "count": count,
        }

    async def upsert_equity_snapshots(self, snapshots: Iterable[dict]) -> int:
        if not snapshots:
            return 0
        payloads = []
        for entry in snapshots:
            captured_at = _ensure_datetime(entry.get("captured_at"))
            if captured_at is None:
                continue
            payloads.append(
                {
                    "captured_at": captured_at,
                    "total_equity": _to_decimal(entry.get("total_equity")),
                    "wallet_balance": _to_decimal(entry.get("wallet_balance")),
                    "available_balance": _to_decimal(entry.get("available_balance")),
                    "currency": entry.get("currency") or "USDT",
                    "created_at": datetime.now(timezone.utc),
                }
            )
        if not payloads:
            return 0

        stmt = pg_insert(AccountEquitySnapshot).values(payloads)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AccountEquitySnapshot.captured_at],
            set_={
                "total_equity": stmt.excluded.total_equity,
                "wallet_balance": stmt.excluded.wallet_balance,
                "available_balance": stmt.excluded.available_balance,
                "currency": stmt.excluded.currency,
                "created_at": stmt.excluded.created_at,
            },
        )
        async with db_session() as session:
            await session.execute(stmt)
        return len(payloads)

    async def upsert_transactions(self, transactions: Iterable[dict]) -> int:
        if not transactions:
            return 0
        payloads = []
        for entry in transactions:
            created_time = _ensure_datetime(
                entry.get("trade_time") or entry.get("created_time")
            )
            if created_time is None:
                continue
            amount_decimal = _to_decimal(entry.get("amount"))
            fee_decimal = _to_decimal(entry.get("fee"))
            if (
                amount_decimal is not None
                and amount_decimal.copy_abs() > MAX_TRANSACTION_ABS_AMOUNT
            ):
                LOGGER.warning(
                    "exchange_tx_amount_out_of_range",
                    transaction_id=entry.get("transaction_id") or entry.get("id"),
                    amount=str(amount_decimal),
                )
                continue
            if (
                fee_decimal is not None
                and fee_decimal.copy_abs() > MAX_TRANSACTION_ABS_AMOUNT
            ):
                LOGGER.warning(
                    "exchange_tx_fee_out_of_range",
                    transaction_id=entry.get("transaction_id") or entry.get("id"),
                    fee=str(fee_decimal),
                )
                continue
            payloads.append(
                {
                    "transaction_id": entry.get("transaction_id"),
                    "reference_id": entry.get("reference_id"),
                    "type": entry.get("type") or "unknown",
                    "sub_type": entry.get("sub_type"),
                    "amount": amount_decimal,
                    "currency": entry.get("currency") or "USDT",
                    "fee": fee_decimal,
                    "created_time": created_time,
                    "created_at": datetime.now(timezone.utc),
                }
            )
        if not payloads:
            return 0

        stmt = pg_insert(AccountTransaction).values(payloads)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AccountTransaction.transaction_id],
            set_={
                "reference_id": stmt.excluded.reference_id,
                "type": stmt.excluded.type,
                "sub_type": stmt.excluded.sub_type,
                "amount": stmt.excluded.amount,
                "currency": stmt.excluded.currency,
                "fee": stmt.excluded.fee,
                "created_time": stmt.excluded.created_time,
                "created_at": stmt.excluded.created_at,
            },
        )
        async with db_session() as session:
            await session.execute(stmt)
        return len(payloads)

    async def last_trade_time(self) -> datetime | None:
        async with db_session() as session:
            stmt = (
                select(ExchangeTrade.trade_time)
                .order_by(ExchangeTrade.trade_time.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        return row

    async def last_transaction_time(self) -> datetime | None:
        async with db_session() as session:
            stmt = (
                select(AccountTransaction.created_time)
                .order_by(AccountTransaction.created_time.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        return row

    async def list_equity_snapshots(
        self,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        filters = []
        if start:
            filters.append(AccountEquitySnapshot.captured_at >= start)
        if end:
            filters.append(AccountEquitySnapshot.captured_at <= end)

        stmt = (
            select(AccountEquitySnapshot)
            .where(*filters)
            .order_by(AccountEquitySnapshot.captured_at.desc())
            .limit(limit)
        )

        async with db_session() as session:
            rows = (await session.execute(stmt)).scalars().all()

        return [
            {
                "captured_at": row.captured_at.isoformat() if row.captured_at else None,
                "total_equity": (
                    float(row.total_equity) if row.total_equity is not None else None
                ),
                "wallet_balance": (
                    float(row.wallet_balance)
                    if row.wallet_balance is not None
                    else None
                ),
                "available_balance": (
                    float(row.available_balance)
                    if row.available_balance is not None
                    else None
                ),
                "currency": row.currency,
            }
            for row in rows
        ]

    async def latest_equity_snapshot(self) -> dict[str, Any] | None:
        stmt = (
            select(AccountEquitySnapshot)
            .order_by(AccountEquitySnapshot.captured_at.desc())
            .limit(1)
        )
        async with db_session() as session:
            row = (await session.execute(stmt)).scalars().first()
        if row is None:
            return None
        return {
            "captured_at": row.captured_at.isoformat() if row.captured_at else None,
            "total_equity": (
                float(row.total_equity) if row.total_equity is not None else None
            ),
            "wallet_balance": (
                float(row.wallet_balance) if row.wallet_balance is not None else None
            ),
            "available_balance": (
                float(row.available_balance)
                if row.available_balance is not None
                else None
            ),
            "currency": row.currency,
        }
