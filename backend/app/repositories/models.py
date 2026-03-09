"""SQLAlchemy models for audit logging."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stream = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class TradeSession(Base):
    __tablename__ = "trade_sessions"

    session_id = Column(String(64), primary_key=True)
    symbol = Column(String(30), nullable=False)
    direction = Column(String(8), nullable=False)
    mode = Column(String(16), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    entry_directive_id = Column(String(80), nullable=False, unique=True)
    exit_directive_id = Column(String(80), nullable=True, unique=True)
    entry_price = Column(Numeric(18, 8), nullable=True)
    entry_qty = Column(Numeric(18, 8), nullable=True)
    exit_price = Column(Numeric(18, 8), nullable=True)
    exit_qty = Column(Numeric(18, 8), nullable=True)
    target_price = Column(Numeric(18, 8), nullable=True)
    stop_price = Column(Numeric(18, 8), nullable=True)
    pnl_usdt = Column(Numeric(18, 8), nullable=True)
    pnl_pct = Column(Numeric(18, 6), nullable=True)
    tp_hit = Column(Boolean, default=False, nullable=False)
    sl_hit = Column(Boolean, default=False, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    risk_reward_ratio = Column(Numeric(18, 6), nullable=True)
    comment = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    fills = relationship("TradeFill", back_populates="session", cascade="all, delete-orphan")


class TradeFill(Base):
    __tablename__ = "trade_fills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("trade_sessions.session_id", ondelete="CASCADE"), nullable=False)
    directive_id = Column(String(80), nullable=False)
    order_id = Column(String(80), nullable=True)
    side = Column(String(8), nullable=True)
    price = Column(Numeric(18, 8), nullable=True)
    quantity = Column(Numeric(18, 8), nullable=True)
    fees = Column(Numeric(18, 8), nullable=True)
    reported_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("TradeSession", back_populates="fills")


class HypothesisSession(Base):
    __tablename__ = "hypothesis_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hypothesis_id = Column(String(80), nullable=False, index=True)
    session_id = Column(String(64), ForeignKey("trade_sessions.session_id", ondelete="CASCADE"), nullable=False, unique=True)
    symbol = Column(String(30), nullable=False)
    direction = Column(String(8), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    pnl_usdt = Column(Numeric(18, 8), nullable=True)
    pnl_pct = Column(Numeric(18, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), nullable=False)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (UniqueConstraint("key", name="uq_runtime_settings_key"),)


class ExchangeTrade(Base):
    __tablename__ = "exchange_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exec_id = Column(String(64), nullable=False, unique=True)
    order_id = Column(String(80), nullable=True, index=True)
    symbol = Column(String(30), nullable=False, index=True)
    side = Column(String(8), nullable=True)
    trade_type = Column(String(32), nullable=True)
    price = Column(Numeric(18, 8), nullable=True)
    quantity = Column(Numeric(18, 8), nullable=True)
    fee = Column(Numeric(18, 8), nullable=True)
    fee_currency = Column(String(16), nullable=True)
    realized_pnl = Column(Numeric(18, 8), nullable=True)
    trade_time = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AccountEquitySnapshot(Base):
    __tablename__ = "account_equity_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, unique=True)
    total_equity = Column(Numeric(18, 8), nullable=True)
    wallet_balance = Column(Numeric(18, 8), nullable=True)
    available_balance = Column(Numeric(18, 8), nullable=True)
    currency = Column(String(16), nullable=False, default="USDT")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AccountTransaction(Base):
    __tablename__ = "account_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(80), nullable=False, unique=True)
    reference_id = Column(String(80), nullable=True)
    type = Column(String(32), nullable=False)
    sub_type = Column(String(32), nullable=True)
    amount = Column(Numeric(18, 8), nullable=True)
    currency = Column(String(16), nullable=False, default="USDT")
    fee = Column(Numeric(18, 8), nullable=True)
    created_time = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

