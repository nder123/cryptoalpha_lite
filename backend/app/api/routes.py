"""FastAPI router definitions."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete

from app.api.deps import (
    get_app_state,
    get_cto_ai,
    get_event_bus,
    get_notifier,
    get_runtime_config_manager,
    get_runtime_settings_repo,
)
from app.core.config import Settings, get_settings
from app.core.runtime_config import (
    RuntimeConfig,
    RuntimeConfigManager,
    RuntimeConfigUpdate,
)
from app.domain import streams
from app.domain.events import (
    CTOAiDecision,
    ExecutionReport,
    PositionEvent,
    RiskAssessment,
    TradeAction,
    TradeDirective,
    TradeHypothesis,
    TradingMode,
)
from app.infrastructure.database import db_session
from app.infrastructure.event_bus import EventBus
from app.repositories.bybit_sync import ExchangeDataRepository
from app.repositories.event_logs import EventLogRepository
from app.repositories.models import (
    AccountEquitySnapshot,
    AccountTransaction,
    ExchangeTrade,
    HypothesisSession,
    TradeFill,
    TradeSession,
)
from app.repositories.runtime_settings import RuntimeSettingsRepository
from app.repositories.trade_stats import TradeStatsRepository
from app.services.rl_trainer import EXPERIENCE_KEY, FORCE_TRAIN_QUEUE, LAST_TRAIN_KEY
from app.state.cto_ai import CTOAIOrchestrator
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState

CLOSED_TRADES_KEY = "rl_metrics:closed_trades"
ACTIVE_VERSION_KEY = "rl_policy:active_version"
POLICY_KEY = "rl_policy:latest"
POLICY_BY_VERSION_PREFIX = "rl_policy:by_version:"


class RLExperienceSample(BaseModel):
    directive_id: str
    symbol: str
    action: str
    timestamp: datetime | None
    reward: float | None
    value: float | None


class RLMetrics(BaseModel):
    timestamp: datetime | None
    total_trades: int | None
    win_rate: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None
    max_drawdown_window: float | None = None
    losses_last_window: int | None
    loss_window_size: int | None = None
    last_trade_pnl_pct: float | None
    last_trade_pnl_pct_used: float | None = None
    last_trade_reward: float | None


class RLPolicySummary(BaseModel):
    version: str | None
    architecture: str | None
    threshold: float | None
    input_size: int | None
    hidden_size: int | None
    action_size: int | None


class ClosedTradeSummary(BaseModel):
    total_pnl_usdt: float | None
    avg_pnl_pct: float | None
    total_trades: int
    winning_trades: int
    win_rate: float
    avg_rr: float | None


class ClosedTradeEntry(BaseModel):
    session_id: str
    symbol: str
    direction: str
    opened_at: datetime | None
    closed_at: datetime | None
    pnl_usdt: float | None
    pnl_pct: float | None
    duration_seconds: int | None
    entry_directive_id: Optional[str]
    exit_directive_id: Optional[str]


class PositionEntry(BaseModel):
    symbol: str
    side: str
    size: float
    entry_price: float | None
    mark_price: float | None
    notional_usdt: float | None
    leverage: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    liquidation_price: float | None
    take_profit: float | None
    stop_loss: float | None
    updated_at: datetime | None


class RLStatusResponse(BaseModel):
    experience_count: int
    experience_oldest: Optional[RLExperienceSample]
    experience_latest: Optional[RLExperienceSample]
    latest_metrics: Optional[RLMetrics]
    policy: Optional[RLPolicySummary]
    active_policy_version: str | None = None
    active_policy: Optional[RLPolicySummary] = None
    closed_summary: Optional[ClosedTradeSummary]
    recent_closed: list[ClosedTradeEntry]
    force_queue_size: int
    buffer_ready: bool
    min_batch_required: int
    last_trained_at: datetime | None
    next_eligible_at: datetime | None


class MaintenanceCleanupResponse(BaseModel):
    status: str
    cleaned_at: datetime
    db_deleted: dict[str, int]
    redis_deleted: list[str]


class RLTrainRequest(BaseModel):
    reason: str | None = None
    priority: Literal["normal", "high"] = "normal"


class RLPolicyPromoteRequest(BaseModel):
    version: str = Field(..., min_length=8)


class ServiceHealthEntry(BaseModel):
    status: str
    updated_at: datetime | None = None
    message: str | None = None
    error: str | None = None

    model_config = {
        "extra": "allow",
    }


class MarketOverview(BaseModel):
    ignored: dict[str, object]
    watch: dict[str, object]
    candidate: dict[str, object]
    active: dict[str, object]


router = APIRouter()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # noqa: F841
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {value}")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/settings", response_model=Settings)
async def read_settings(settings: Settings = Depends(get_settings)) -> Settings:
    return settings


@router.get("/config/runtime", response_model=RuntimeConfig)
async def read_runtime_config(
    manager: RuntimeConfigManager = Depends(get_runtime_config_manager),
    store: GlobalAppState = Depends(get_app_state),
) -> RuntimeConfig:
    config = await manager.get_config()
    await store.set_runtime_config(config)
    return config


@router.get("/config/risk-budget")
async def read_risk_budget(
    store: GlobalAppState = Depends(get_app_state),
) -> dict[str, Any]:
    return await store.get_risk_budget()


@router.patch("/config/runtime", response_model=RuntimeConfig)
async def update_runtime_config(
    payload: RuntimeConfigUpdate,
    manager: RuntimeConfigManager = Depends(get_runtime_config_manager),
    store: GlobalAppState = Depends(get_app_state),
    notifier: BroadcastManager = Depends(get_notifier),
    settings_repo: RuntimeSettingsRepository = Depends(get_runtime_settings_repo),
) -> RuntimeConfig:
    updates = payload.to_updates()
    if not updates:
        return await manager.get_config()
    previous_overrides = await manager.export_overrides()
    config = await manager.update(updates)
    overrides = await manager.export_overrides()
    if overrides != previous_overrides:
        await settings_repo.upsert_overrides(overrides)
    await store.set_runtime_config(config)
    await notifier.broadcast(await store.build_dashboard_state())
    return config


@router.get("/market/overview", response_model=MarketOverview)
async def market_overview(
    state: GlobalAppState = Depends(get_app_state),
) -> MarketOverview:
    overview = await state.list_market()
    return MarketOverview(
        ignored=overview.ignored,
        watch=overview.watch,
        candidate=overview.candidate,
        active=overview.active,
    )


@router.get("/services/health", response_model=dict[str, ServiceHealthEntry])
async def services_health(
    state: GlobalAppState = Depends(get_app_state),
) -> dict[str, ServiceHealthEntry]:
    health = await state.get_service_health()
    return {name: ServiceHealthEntry(**payload) for name, payload in health.items()}


@router.get("/ctoai/state")
async def ctoai_state(
    cto_ai: CTOAIOrchestrator = Depends(get_cto_ai),
) -> dict[str, object]:
    return await cto_ai.snapshot()


class ModeRequest(BaseModel):
    mode: TradingMode


class ManualDirectiveRequest(BaseModel):
    symbol: str = Field(..., min_length=2, max_length=30)
    direction: Literal["long", "short"]
    action: Literal["open", "close"] = "open"
    order_type: Literal["market", "limit"] = "market"
    quantity: float = Field(..., gt=0)
    price: float | None = Field(default=None, gt=0)
    time_in_force: Literal["GTC", "IOC", "FOK"] = "GTC"
    take_profit_price: float | None = Field(default=None, gt=0)
    stop_loss_price: float | None = Field(default=None, gt=0)
    reduce_only: bool | None = None
    leverage: float = Field(default=1.0, gt=0, le=50)
    confidence: float | None = Field(default=None, ge=0, le=1)
    expires_in_minutes: int | None = Field(default=None, ge=1, le=60)


class StreamEventResponse(BaseModel):
    id: str
    stream: str
    event_type: str
    timestamp: datetime | None
    data: dict[str, Any]


@router.get("/ctoai/directives", response_model=list[TradeDirective])
async def list_directives(
    state: GlobalAppState = Depends(get_app_state),
) -> list[TradeDirective]:
    return await state.list_directives()


@router.get("/ctoai/rejections")
async def list_rejections(
    state: GlobalAppState = Depends(get_app_state),
) -> list[dict[str, object]]:
    return await state.list_rejections()


@router.post("/ctoai/rejections/clear")
async def clear_rejections(
    store: GlobalAppState = Depends(get_app_state),
    notifier: BroadcastManager = Depends(get_notifier),
) -> dict[str, int]:
    cleared = await store.clear_rejections()
    await notifier.broadcast(await store.build_dashboard_state())
    return {"cleared": cleared}


@router.get("/exchange/positions", response_model=list[PositionEntry])
async def list_positions(
    state: GlobalAppState = Depends(get_app_state),
) -> list[PositionEntry]:
    entries = await state.list_positions()
    return [PositionEntry(**entry) for entry in entries]


@router.post("/ctoai/mode")
async def set_mode(
    payload: ModeRequest,
    cto_ai: CTOAIOrchestrator = Depends(get_cto_ai),
    store: GlobalAppState = Depends(get_app_state),
    notifier: BroadcastManager = Depends(get_notifier),
) -> dict[str, object]:
    await cto_ai.set_mode(payload.mode)
    await store.set_ctoai_snapshot(await cto_ai.snapshot())
    await notifier.broadcast(await store.build_dashboard_state())
    return await cto_ai.snapshot()


@router.post("/ctoai/manual-directive", response_model=TradeDirective)
async def create_manual_directive(
    payload: ManualDirectiveRequest,
    store: GlobalAppState = Depends(get_app_state),
    notifier: BroadcastManager = Depends(get_notifier),
    bus: EventBus = Depends(get_event_bus),
    orchestrator: CTOAIOrchestrator = Depends(get_cto_ai),
) -> TradeDirective:
    if payload.order_type == "limit" and payload.price is None:
        raise HTTPException(
            status_code=400, detail="Price is required for limit orders"
        )

    reduce_only = (
        payload.reduce_only
        if payload.reduce_only is not None
        else payload.action == "close"
    )

    price = payload.price if payload.order_type == "limit" else None
    take_profit = payload.take_profit_price if payload.action == "open" else None
    stop_loss = payload.stop_loss_price if payload.action == "open" else None

    now = datetime.now(timezone.utc)
    expires_at = (
        now + timedelta(minutes=payload.expires_in_minutes)
        if payload.expires_in_minutes
        else None
    )

    confidence = payload.confidence if payload.confidence is not None else 1.0

    directive = TradeDirective(
        directive_id=f"manual-{uuid4().hex}",
        hypothesis_id=None,
        symbol=payload.symbol.upper(),
        issued_at=now,
        action=TradeAction(payload.action),
        rationale=["Manual directive"],
        mode=TradingMode.MANUAL,
        confidence=confidence,
        direction=payload.direction,
        order_type=payload.order_type,
        quantity=payload.quantity,
        price=price,
        time_in_force=payload.time_in_force,
        leverage=payload.leverage,
        reduce_only=reduce_only,
        notional_usdt=(price or 0.0) * payload.quantity,
        expires_at=expires_at,
        take_profit_price=take_profit,
        stop_loss_price=stop_loss,
    )

    decision = orchestrator.build_decision(
        directive,
        source="operator",
        meta={"request_id": directive.directive_id, "reason": "manual"},
    )
    await store.upsert_directive(directive)
    await bus.publish(streams.CTOAI_DIRECTIVES, directive)
    await bus.publish(streams.CTOAI_DECISIONS, decision)
    await notifier.broadcast(await store.build_dashboard_state())
    return directive


@router.get("/stats/trades")
async def list_trade_stats(
    start: str | None = Query(
        default=None, description="ISO datetime inclusive lower bound"
    ),
    end: str | None = Query(
        default=None, description="ISO datetime inclusive upper bound"
    ),
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    repo = TradeStatsRepository()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    return await repo.list_sessions(
        start=start_dt, end=end_dt, symbol=symbol, limit=limit, offset=offset
    )


@router.get("/stats/trades/summary")
async def trade_stats_summary(
    start: str | None = Query(
        default=None, description="ISO datetime inclusive lower bound"
    ),
    end: str | None = Query(
        default=None, description="ISO datetime inclusive upper bound"
    ),
) -> dict[str, object]:
    repo = TradeStatsRepository()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    summary = await repo.compute_summary(start=start_dt, end=end_dt)
    daily = await repo.aggregate_period("day", start=start_dt, end=end_dt)
    weekly = await repo.aggregate_period("week", start=start_dt, end=end_dt)
    return {
        "summary": summary,
        "daily": daily,
        "weekly": weekly,
    }


class TradeDashboardOverview(BaseModel):
    summary: dict[str, Any] | None
    recent: list[dict[str, Any]]
    last_trade: dict[str, Any] | None
    updated_at: datetime | None


class WorstTradeSessionEntry(BaseModel):
    session_id: str
    symbol: str
    direction: str
    mode: str | None = None
    opened_at: datetime | None
    closed_at: datetime | None
    entry_price: float | None
    exit_price: float | None
    pnl_usdt: float | None
    fees_usdt: float | None
    pnl_usdt_net: float | None
    pnl_pct: float | None
    tp_hit: bool | None = None
    sl_hit: bool | None = None
    duration_seconds: int | None
    risk_reward_ratio: float | None
    entry_directive_id: str | None
    exit_directive_id: str | None
    comment: str | None


class ExchangeTradeEntry(BaseModel):
    exec_id: str
    order_id: str | None
    symbol: str
    side: str | None
    trade_type: str | None
    price: float | None
    quantity: float | None
    fee: float | None
    fee_currency: str | None
    realized_pnl: float | None
    trade_time: datetime | None


class ExchangeTradeListResponse(BaseModel):
    total: int
    items: list[ExchangeTradeEntry]


class ExchangeTradeSummary(BaseModel):
    realized_pnl: float
    fees: float
    count: int


class AccountTransactionEntry(BaseModel):
    transaction_id: str
    reference_id: str | None
    type: str
    sub_type: str | None
    amount: float | None
    currency: str | None
    fee: float | None
    created_time: datetime | None


class AccountTransactionListResponse(BaseModel):
    total: int
    items: list[AccountTransactionEntry]


class AccountTransactionSummary(BaseModel):
    amount: float
    fees: float
    count: int


class EquitySnapshotEntry(BaseModel):
    captured_at: datetime | None
    total_equity: float | None
    wallet_balance: float | None
    available_balance: float | None
    currency: str | None


class HypothesisPnlEntry(BaseModel):
    hypothesis_id: str
    symbol: str | None
    direction: str | None
    trades: int
    total_pnl_usdt: float | None
    avg_pnl_pct: float | None
    last_closed_at: datetime | None


@router.get("/stats/trades/dashboard", response_model=TradeDashboardOverview)
async def trade_dashboard_overview(
    start: str | None = Query(
        default=None, description="ISO datetime inclusive lower bound"
    ),
    end: str | None = Query(
        default=None, description="ISO datetime inclusive upper bound"
    ),
    state: GlobalAppState = Depends(get_app_state),
) -> TradeDashboardOverview:
    overview = await state.get_trade_stats_overview()
    # If cache empty or filtered range provided, recompute on demand.
    if overview["summary"] is None or start or end:
        repo = TradeStatsRepository()
        start_dt = _parse_datetime(start)
        end_dt = _parse_datetime(end)
        overview = await repo.dashboard_overview(start=start_dt, end=end_dt)
        overview["updated_at"] = datetime.now(timezone.utc).isoformat()
        await state.set_trade_stats_overview(overview)
    return TradeDashboardOverview(**overview)


@router.get("/stats/trades/worst", response_model=list[WorstTradeSessionEntry])
async def list_worst_closed_trades(
    start: str | None = Query(
        default=None, description="ISO datetime inclusive lower bound"
    ),
    end: str | None = Query(
        default=None, description="ISO datetime inclusive upper bound"
    ),
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[WorstTradeSessionEntry]:
    repo = TradeStatsRepository()
    rows = await repo.list_worst_closed(
        start=_parse_datetime(start),
        end=_parse_datetime(end),
        symbol=symbol,
        limit=limit,
    )
    return [
        WorstTradeSessionEntry(
            session_id=item["session_id"],
            symbol=item["symbol"],
            direction=item["direction"],
            mode=item.get("mode"),
            opened_at=(
                datetime.fromisoformat(item["opened_at"])
                if item.get("opened_at")
                else None
            ),
            closed_at=(
                datetime.fromisoformat(item["closed_at"])
                if item.get("closed_at")
                else None
            ),
            entry_price=item.get("entry_price"),
            exit_price=item.get("exit_price"),
            pnl_usdt=item.get("pnl_usdt"),
            fees_usdt=item.get("fees_usdt"),
            pnl_usdt_net=item.get("pnl_usdt_net"),
            pnl_pct=item.get("pnl_pct"),
            tp_hit=item.get("tp_hit"),
            sl_hit=item.get("sl_hit"),
            duration_seconds=item.get("duration_seconds"),
            risk_reward_ratio=item.get("risk_reward_ratio"),
            entry_directive_id=item.get("entry_directive_id"),
            exit_directive_id=item.get("exit_directive_id"),
            comment=item.get("comment"),
        )
        for item in rows
    ]


@router.get("/stats/trades/export")
async def export_trade_stats(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> StreamingResponse:
    repo = TradeStatsRepository()
    rows = await repo.export_sessions(
        start=_parse_datetime(start), end=_parse_datetime(end), symbol=symbol
    )

    def iter_rows() -> asyncio.Iterator[str]:  # type: ignore[type-arg]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in rows:
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow(row)
            yield buffer.getvalue()

    filename_parts = ["trade_stats"]
    if start:
        filename_parts.append(f"from-{start.replace(':', '-')}")
    if end:
        filename_parts.append(f"to-{end.replace(':', '-')}")
    if symbol:
        filename_parts.append(symbol)
    filename = "_".join(filename_parts) + ".csv"
    return StreamingResponse(
        iter_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/exchange/trades", response_model=ExchangeTradeListResponse)
async def list_exchange_trades(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ExchangeTradeListResponse:
    repo = ExchangeDataRepository()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    result = await repo.list_trades(
        start=start_dt, end=end_dt, symbol=symbol, limit=limit, offset=offset
    )
    return ExchangeTradeListResponse(
        total=int(result["total"]),
        items=[ExchangeTradeEntry(**item) for item in result["items"]],
    )


@router.get("/exchange/trades/summary", response_model=ExchangeTradeSummary)
async def exchange_trade_summary(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    symbol: str | None = Query(default=None, min_length=2, max_length=30),
) -> ExchangeTradeSummary:
    repo = ExchangeDataRepository()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    summary = await repo.summarize_trades(start=start_dt, end=end_dt, symbol=symbol)
    return ExchangeTradeSummary(**summary)


@router.get("/exchange/transactions", response_model=AccountTransactionListResponse)
async def list_account_transactions(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    tx_type: str | None = Query(default=None, min_length=1, max_length=32),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AccountTransactionListResponse:
    repo = ExchangeDataRepository()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    result = await repo.list_transactions(
        start=start_dt, end=end_dt, tx_type=tx_type, limit=limit, offset=offset
    )
    return AccountTransactionListResponse(
        total=int(result["total"]),
        items=[AccountTransactionEntry(**item) for item in result["items"]],
    )


@router.get("/exchange/transactions/summary", response_model=AccountTransactionSummary)
async def account_transaction_summary(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    tx_type: str | None = Query(default=None, min_length=1, max_length=32),
) -> AccountTransactionSummary:
    repo = ExchangeDataRepository()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    summary = await repo.summarize_transactions(
        start=start_dt, end=end_dt, tx_type=tx_type
    )
    return AccountTransactionSummary(**summary)


@router.get("/exchange/equity", response_model=list[EquitySnapshotEntry])
async def list_equity_snapshots(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[EquitySnapshotEntry]:
    repo = ExchangeDataRepository()
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    snapshots = await repo.list_equity_snapshots(
        start=start_dt, end=end_dt, limit=limit
    )
    return [EquitySnapshotEntry(**entry) for entry in snapshots]


@router.get("/exchange/equity/latest", response_model=EquitySnapshotEntry | None)
async def latest_equity_snapshot() -> EquitySnapshotEntry | None:
    repo = ExchangeDataRepository()
    snapshot = await repo.latest_equity_snapshot()
    return EquitySnapshotEntry(**snapshot) if snapshot else None


@router.get("/stats/hypotheses/pnl", response_model=list[HypothesisPnlEntry])
async def list_hypothesis_pnl(
    limit: int = Query(default=100, ge=1, le=500),
) -> list[HypothesisPnlEntry]:
    repo = TradeStatsRepository()
    rows = await repo.list_hypothesis_stats(limit=limit)
    return [
        HypothesisPnlEntry(
            hypothesis_id=item["hypothesis_id"],
            symbol=item.get("symbol"),
            direction=item.get("direction"),
            trades=int(item.get("trades", 0)),
            total_pnl_usdt=item.get("total_pnl_usdt"),
            avg_pnl_pct=item.get("avg_pnl_pct"),
            last_closed_at=(
                datetime.fromisoformat(item["last_closed_at"])
                if item.get("last_closed_at")
                else None
            ),
        )
        for item in rows
    ]


async def _stream_events(
    stream: str,
    model: type[BaseModel],
    *,
    limit: int,
    after_id: str | None,
    bus: EventBus,
) -> list[StreamEventResponse]:
    if after_id:
        raw = await bus.fetch_after(stream, after_id=after_id, limit=limit)
    else:
        raw = list(reversed(await bus.fetch_recent(stream, limit=limit)))

    events: list[StreamEventResponse] = []
    for item in raw:
        data_payload = item.get("data") or {}
        try:
            payload = model.model_validate(data_payload)
            data_dict = payload.model_dump(mode="json")
        except ValidationError:
            data_dict = data_payload if isinstance(data_payload, dict) else {}
        timestamp_raw = item.get("timestamp")
        timestamp_value: datetime | None = None
        if isinstance(timestamp_raw, str):
            try:
                timestamp_value = datetime.fromisoformat(timestamp_raw)
            except ValueError:
                timestamp_value = None
        events.append(
            StreamEventResponse(
                id=str(item.get("id", "")),
                stream=stream,
                event_type=str(item.get("event_type", model.__name__)),
                timestamp=timestamp_value,
                data=data_dict,
            )
        )
    return events


@router.get("/streams/execution", response_model=list[StreamEventResponse])
async def list_execution_events(
    limit: int = Query(default=100, ge=1, le=500),
    after_id: str | None = Query(
        default=None, description="Return entries strictly after this ID"
    ),
    bus: EventBus = Depends(get_event_bus),
) -> list[StreamEventResponse]:
    return await _stream_events(
        streams.EXECUTION_REPORTS,
        ExecutionReport,
        limit=limit,
        after_id=after_id,
        bus=bus,
    )


@router.get("/ops/duty-check")
async def ops_duty_check(
    store: GlobalAppState = Depends(get_app_state),
    cto_ai: CTOAIOrchestrator = Depends(get_cto_ai),
    bus: EventBus = Depends(get_event_bus),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    issues: list[str] = []
    warnings: list[str] = []

    health = await store.get_service_health()
    bad_statuses = {"error", "degraded", "stopped", "unknown"}
    bad_services = sorted(
        name
        for name, payload in health.items()
        if str(payload.get("status", "unknown")).lower() in bad_statuses
    )
    if bad_services:
        issues.append(f"services_not_healthy={','.join(bad_services)}")

    ctoai_snapshot = await cto_ai.snapshot()
    ctoai_mode = str(ctoai_snapshot.get("mode") or "unknown")
    active_directives = ctoai_snapshot.get("active_directives")
    active_count = len(active_directives) if isinstance(active_directives, list) else 0
    if active_count > 0:
        issues.append(f"active_directives={active_count}")

    ctoai_state = str(ctoai_snapshot.get("state") or "unknown")
    if ctoai_state == "awaiting_execution" and not issues:
        warnings.append("ctoai_state=awaiting_execution")

    expect_execution_activity = not (
        ctoai_mode == "manual" and ctoai_state == "idle" and active_count == 0
    )

    execution_last_id: str | None = None
    execution_last_timestamp: str | None = None
    execution_age_seconds: float | None = None
    raw = await bus.fetch_recent(streams.EXECUTION_REPORTS, limit=1)
    if raw:
        execution_last_id = str(raw[0].get("id") or "") or None
        execution_last_timestamp = raw[0].get("timestamp")
        if isinstance(execution_last_timestamp, str):
            try:
                ts = datetime.fromisoformat(execution_last_timestamp)
            except ValueError:
                ts = None
            if ts is not None:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                execution_age_seconds = (now - ts).total_seconds()
    else:
        if expect_execution_activity:
            issues.append("execution_stream_empty")

    if execution_age_seconds is not None:
        if execution_age_seconds > 1800:
            # Execution stream can become quiet in dry-run when the autopilot is intentionally
            # blocked by anti-ruin limits. In that case, we don't want to page on-call.
            if not expect_execution_activity:
                pass
            elif active_count == 0 and ctoai_state != "awaiting_execution":
                warnings.append(
                    f"execution_stream_stale_s={int(execution_age_seconds)}"
                )
            else:
                issues.append(f"execution_stream_stale_s={int(execution_age_seconds)}")
        elif execution_age_seconds > 600:
            if expect_execution_activity:
                warnings.append(
                    f"execution_stream_stale_s={int(execution_age_seconds)}"
                )

    rl_active_version: str | None = None
    rl_latest_version: str | None = None
    rl_loaded: dict[str, object] | None = None
    rl_verdict: str = "unknown"
    rl_details: list[str] = []

    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    try:
        rl_active_version = await client.get(ACTIVE_VERSION_KEY)
        policy_raw = await client.get(POLICY_KEY)
    finally:
        await client.aclose()

    if policy_raw:
        try:
            payload = json.loads(policy_raw)
            if isinstance(payload, dict):
                rl_latest_version = payload.get("version")
        except json.JSONDecodeError:
            rl_latest_version = None

    rl_loaded = await cto_ai.rl_policy_metadata()
    loaded_policy_version = None
    loaded_active_version = None
    loaded_redis_key = None
    if isinstance(rl_loaded, dict):
        loaded_policy_version = rl_loaded.get("policy_version")
        loaded_active_version = rl_loaded.get("active_policy_version")
        loaded_redis_key = rl_loaded.get("redis_key")

    if not rl_active_version or not rl_latest_version:
        rl_verdict = "attention"
        rl_details.append("missing_versions")
    elif rl_active_version != rl_latest_version:
        rl_verdict = "attention"
        rl_details.append("latest!=active")
    else:
        rl_verdict = "ok"

    if (
        loaded_active_version
        and rl_active_version
        and loaded_active_version != rl_active_version
    ):
        rl_verdict = "attention"
        rl_details.append("loaded_active!=status_active")

    if (
        loaded_policy_version
        and loaded_active_version
        and loaded_policy_version != loaded_active_version
    ):
        rl_verdict = "attention"
        rl_details.append("loaded_policy_version!=active")

    if loaded_redis_key and rl_active_version:
        expected_key = f"{POLICY_BY_VERSION_PREFIX}{rl_active_version}"
        if loaded_redis_key != expected_key:
            rl_verdict = "attention"
            rl_details.append("loaded_redis_key!=by_version")

    if rl_details:
        if any(
            item
            in {
                "loaded_policy_version!=active",
                "loaded_redis_key!=by_version",
                "loaded_active!=status_active",
            }
            for item in rl_details
        ):
            issues.append(f"rl_verdict={rl_verdict}:{','.join(rl_details)}")
        else:
            warnings.append(f"rl_verdict={rl_verdict}:{','.join(rl_details)}")

    status = "ok"
    if issues:
        status = "alert"
    elif warnings:
        status = "warn"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "services_bad": bad_services,
        "rl": {
            "verdict": rl_verdict,
            "details": rl_details,
            "active_policy_version": rl_active_version,
            "latest_policy_version": rl_latest_version,
            "loaded": rl_loaded,
        },
        "ctoai": {
            "mode": ctoai_snapshot.get("mode"),
            "state": ctoai_state,
            "active_directives": active_count,
        },
        "execution": {
            "last_id": execution_last_id,
            "last_timestamp": execution_last_timestamp,
            "age_seconds": execution_age_seconds,
        },
        "checked_at": now.isoformat(),
    }


@router.get("/streams/positions", response_model=list[StreamEventResponse])
async def list_position_events(
    limit: int = Query(default=100, ge=1, le=500),
    after_id: str | None = Query(
        default=None, description="Return entries strictly after this ID"
    ),
    bus: EventBus = Depends(get_event_bus),
) -> list[StreamEventResponse]:
    return await _stream_events(
        streams.POSITION_EVENTS, PositionEvent, limit=limit, after_id=after_id, bus=bus
    )


@router.get("/streams/decisions", response_model=list[StreamEventResponse])
async def list_decision_events(
    limit: int = Query(default=100, ge=1, le=500),
    after_id: str | None = Query(
        default=None, description="Return entries strictly after this ID"
    ),
    bus: EventBus = Depends(get_event_bus),
) -> list[StreamEventResponse]:
    return await _stream_events(
        streams.CTOAI_DECISIONS, CTOAiDecision, limit=limit, after_id=after_id, bus=bus
    )


@router.get("/streams/risk", response_model=list[StreamEventResponse])
async def list_risk_events(
    limit: int = Query(default=100, ge=1, le=500),
    after_id: str | None = Query(
        default=None, description="Return entries strictly after this ID"
    ),
    bus: EventBus = Depends(get_event_bus),
) -> list[StreamEventResponse]:
    return await _stream_events(
        streams.RISK_ASSESSMENTS,
        RiskAssessment,
        limit=limit,
        after_id=after_id,
        bus=bus,
    )


@router.get("/streams/hypotheses", response_model=list[StreamEventResponse])
async def list_hypothesis_events(
    limit: int = Query(default=100, ge=1, le=500),
    after_id: str | None = Query(
        default=None, description="Return entries strictly after this ID"
    ),
    bus: EventBus = Depends(get_event_bus),
) -> list[StreamEventResponse]:
    return await _stream_events(
        streams.RESEARCH_HYPOTHESES,
        TradeHypothesis,
        limit=limit,
        after_id=after_id,
        bus=bus,
    )


@router.post("/ctoai/emergency-stop")
async def emergency_stop(
    cto_ai: CTOAIOrchestrator = Depends(get_cto_ai),
    store: GlobalAppState = Depends(get_app_state),
    notifier: BroadcastManager = Depends(get_notifier),
) -> dict[str, object]:
    await cto_ai.emergency_stop()
    await store.set_ctoai_snapshot(await cto_ai.snapshot())
    await notifier.broadcast(await store.build_dashboard_state())
    return await cto_ai.snapshot()


@router.get("/audit/events")
async def list_events(limit: int = 100) -> list[dict[str, object]]:
    repo = EventLogRepository()
    return await repo.fetch_recent(limit)


@router.get("/rl/status", response_model=RLStatusResponse)
async def rl_status(
    settings: Settings = Depends(get_settings),
    manager: RuntimeConfigManager = Depends(get_runtime_config_manager),
) -> RLStatusResponse:
    config = await manager.get_config()
    min_batch_required = max(32, config.rl_retrain_interval_hours * 16)
    train_interval = timedelta(hours=config.rl_retrain_interval_hours)

    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    try:
        experience_count = await client.llen(EXPERIENCE_KEY)
        queue_size = await client.llen(FORCE_TRAIN_QUEUE)
        oldest_raw = await client.lindex(EXPERIENCE_KEY, 0)
        latest_raw = await client.lindex(EXPERIENCE_KEY, -1)
        metrics_raw = await client.get("rl_metrics:latest")
        policy_raw = await client.get(POLICY_KEY)
        active_policy_version = await client.get(ACTIVE_VERSION_KEY)
        active_policy_raw = None
        if active_policy_version:
            active_policy_raw = await client.get(
                f"{POLICY_BY_VERSION_PREFIX}{active_policy_version}"
            )
        closed_raw = await client.lrange(CLOSED_TRADES_KEY, 0, 19)
        last_train_raw = await client.get(LAST_TRAIN_KEY)
    finally:
        await client.aclose()

    last_trained_at: datetime | None = None
    if last_train_raw:
        try:
            last_trained_at = datetime.fromisoformat(last_train_raw)
        except ValueError:
            last_trained_at = None

    buffer_ready = experience_count >= min_batch_required
    now = datetime.now(timezone.utc)
    base_time = last_trained_at or now
    next_eligible_at = (
        base_time + train_interval if train_interval.total_seconds() > 0 else None
    )

    def _parse_experience(raw: str | None) -> RLExperienceSample | None:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        timestamp_raw: Any = payload.get("timestamp")
        timestamp_value: datetime | None = None
        if isinstance(timestamp_raw, str):
            try:
                timestamp_value = datetime.fromisoformat(timestamp_raw)
            except ValueError:
                timestamp_value = None
        return RLExperienceSample(
            directive_id=str(payload.get("directive_id", "")),
            symbol=str(payload.get("symbol", "")),
            action=str(payload.get("action", "")),
            timestamp=timestamp_value,
            reward=(
                float(payload.get("reward"))
                if payload.get("reward") is not None
                else None
            ),
            value=(
                float(payload.get("value"))
                if payload.get("value") is not None
                else None
            ),
        )

    def _parse_metrics(raw: str | None) -> RLMetrics | None:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        timestamp_value: datetime | None = None
        if isinstance(payload.get("timestamp"), str):
            try:
                timestamp_value = datetime.fromisoformat(payload["timestamp"])
            except ValueError:
                timestamp_value = None
        return RLMetrics(
            timestamp=timestamp_value,
            total_trades=(
                int(payload.get("total_trades", 0))
                if payload.get("total_trades") is not None
                else None
            ),
            win_rate=(
                float(payload.get("win_rate"))
                if payload.get("win_rate") is not None
                else None
            ),
            sharpe_ratio=(
                float(payload.get("sharpe_ratio"))
                if payload.get("sharpe_ratio") is not None
                else None
            ),
            max_drawdown=(
                float(payload.get("max_drawdown"))
                if payload.get("max_drawdown") is not None
                else None
            ),
            max_drawdown_window=(
                float(payload.get("max_drawdown_window"))
                if payload.get("max_drawdown_window") is not None
                else None
            ),
            losses_last_window=(
                int(payload.get("losses_last_window", 0))
                if payload.get("losses_last_window") is not None
                else None
            ),
            loss_window_size=(
                int(payload.get("loss_window_size"))
                if payload.get("loss_window_size") is not None
                else None
            ),
            last_trade_pnl_pct=(
                float(payload.get("last_trade_pnl_pct"))
                if payload.get("last_trade_pnl_pct") is not None
                else None
            ),
            last_trade_pnl_pct_used=(
                float(payload.get("last_trade_pnl_pct_used"))
                if payload.get("last_trade_pnl_pct_used") is not None
                else None
            ),
            last_trade_reward=(
                float(payload.get("last_trade_reward"))
                if payload.get("last_trade_reward") is not None
                else None
            ),
        )

    def _parse_policy(raw: str | None) -> RLPolicySummary | None:
        if not raw:
            return None
        try:
            payload: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return RLPolicySummary(
            version=payload.get("version"),
            architecture=payload.get("architecture"),
            threshold=(
                float(payload.get("threshold"))
                if payload.get("threshold") is not None
                else None
            ),
            input_size=(
                int(payload.get("input_size"))
                if payload.get("input_size") is not None
                else None
            ),
            hidden_size=(
                int(payload.get("hidden_size"))
                if payload.get("hidden_size") is not None
                else None
            ),
            action_size=(
                int(payload.get("action_size"))
                if payload.get("action_size") is not None
                else None
            ),
        )

    def _parse_closed_entry(raw: str) -> ClosedTradeEntry | None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None

        def _safe_datetime(value: Any) -> datetime | None:
            if not value or not isinstance(value, str):
                return None
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None

        return ClosedTradeEntry(
            session_id=str(payload.get("session_id", "")),
            symbol=str(payload.get("symbol", "")),
            direction=str(payload.get("direction", "")),
            opened_at=_safe_datetime(payload.get("opened_at")),
            closed_at=_safe_datetime(payload.get("closed_at")),
            pnl_usdt=(
                float(payload.get("pnl_usdt"))
                if payload.get("pnl_usdt") is not None
                else None
            ),
            pnl_pct=(
                float(payload.get("pnl_pct"))
                if payload.get("pnl_pct") is not None
                else None
            ),
            duration_seconds=(
                int(payload.get("duration_seconds"))
                if payload.get("duration_seconds") is not None
                else None
            ),
            entry_directive_id=payload.get("entry_directive_id"),
            exit_directive_id=payload.get("exit_directive_id"),
        )

    repo = TradeStatsRepository()
    summary_data: dict[str, Any] | None = None
    recent_db: list[dict[str, Any]] = []
    try:
        summary_data = await repo.compute_summary()
        recent_db = await repo.list_recent_closed(limit=20)
    except Exception:
        summary_data = None
        recent_db = []

    def _build_summary(data: dict[str, Any] | None) -> ClosedTradeSummary | None:
        if not data:
            return None
        return ClosedTradeSummary(
            total_pnl_usdt=data.get("total_pnl_usdt"),
            avg_pnl_pct=data.get("avg_pnl_pct"),
            total_trades=int(data.get("total_trades", 0)),
            winning_trades=int(data.get("winning_trades", 0)),
            win_rate=float(data.get("win_rate", 0.0)),
            avg_rr=data.get("avg_rr"),
        )

    closed_summary = _build_summary(summary_data)

    def _map_recent_row(row: dict[str, Any]) -> ClosedTradeEntry:
        def _safe_datetime(value: Any) -> datetime | None:
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    return None
            return None

        return ClosedTradeEntry(
            session_id=str(row.get("session_id", "")),
            symbol=str(row.get("symbol", "")),
            direction=str(row.get("direction", "")),
            opened_at=_safe_datetime(row.get("opened_at")),
            closed_at=_safe_datetime(row.get("closed_at")),
            pnl_usdt=(
                float(row.get("pnl_usdt")) if row.get("pnl_usdt") is not None else None
            ),
            pnl_pct=(
                float(row.get("pnl_pct")) if row.get("pnl_pct") is not None else None
            ),
            duration_seconds=(
                int(row.get("duration_seconds"))
                if row.get("duration_seconds") is not None
                else None
            ),
            entry_directive_id=row.get("entry_directive_id"),
            exit_directive_id=row.get("exit_directive_id"),
        )

    if recent_db:
        recent_closed = [_map_recent_row(item) for item in recent_db]
    else:
        recent_closed = [
            entry
            for entry in (_parse_closed_entry(item) for item in closed_raw)
            if entry is not None
        ]

    return RLStatusResponse(
        experience_count=experience_count,
        experience_oldest=_parse_experience(oldest_raw),
        experience_latest=_parse_experience(latest_raw),
        latest_metrics=_parse_metrics(metrics_raw),
        policy=_parse_policy(policy_raw),
        active_policy_version=active_policy_version,
        active_policy=_parse_policy(active_policy_raw) if active_policy_raw else None,
        closed_summary=closed_summary,
        recent_closed=recent_closed,
        force_queue_size=queue_size,
        buffer_ready=buffer_ready,
        min_batch_required=min_batch_required,
        last_trained_at=last_trained_at,
        next_eligible_at=next_eligible_at,
    )


@router.get("/rl/policy/loaded")
async def rl_policy_loaded(
    cto_ai: CTOAIOrchestrator = Depends(get_cto_ai),
) -> dict[str, object]:
    meta = await cto_ai.rl_policy_metadata()
    if meta is None:
        raise HTTPException(status_code=503, detail="RL evaluator is not configured")
    return meta


@router.post("/rl/policy/promote")
async def rl_policy_promote(
    payload: RLPolicyPromoteRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    try:
        raw = await client.get(f"{POLICY_BY_VERSION_PREFIX}{payload.version}")
        if raw is None:
            latest_raw = await client.get(POLICY_KEY)
            if latest_raw:
                try:
                    latest_payload: dict[str, Any] = json.loads(latest_raw)
                except json.JSONDecodeError:
                    latest_payload = {}
                latest_version = (
                    str(latest_payload.get("version")) if latest_payload else ""
                )
                if latest_version and latest_version == payload.version:
                    await client.set(
                        f"{POLICY_BY_VERSION_PREFIX}{payload.version}", latest_raw
                    )
                    raw = latest_raw

        if raw is None:
            raise HTTPException(
                status_code=404, detail=f"Policy version not found: {payload.version}"
            )
        await client.set(ACTIVE_VERSION_KEY, payload.version)
    finally:
        await client.aclose()
    return {"status": "ok", "active_policy_version": payload.version}


@router.get("/rl/policy/exists")
async def rl_policy_exists(
    version: str = Query(..., min_length=8),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    try:
        raw = await client.get(f"{POLICY_BY_VERSION_PREFIX}{version}")
        if raw is not None:
            return {"version": version, "exists": True}

        latest_raw = await client.get(POLICY_KEY)
        if not latest_raw:
            return {"version": version, "exists": False}

        try:
            latest_payload: dict[str, Any] = json.loads(latest_raw)
        except json.JSONDecodeError:
            return {"version": version, "exists": False}

        latest_version = str(latest_payload.get("version")) if latest_payload else ""
        return {
            "version": version,
            "exists": bool(latest_version and latest_version == version),
        }
    finally:
        await client.aclose()


@router.post("/rl/train")
async def trigger_rl_training(
    payload: RLTrainRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    request_payload = {
        "reason": (payload.reason if payload else None),
        "priority": (payload.priority if payload else "normal"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await client.rpush(FORCE_TRAIN_QUEUE, json.dumps(request_payload))
        queue_size = await client.llen(FORCE_TRAIN_QUEUE)
    finally:
        await client.aclose()
    return {
        "status": "queued",
        "queued_at": request_payload["timestamp"],
        "queue_size": queue_size,
        "priority": request_payload["priority"],
    }


@router.post("/maintenance/cleanup", response_model=MaintenanceCleanupResponse)
async def maintenance_cleanup(
    *,
    confirm: bool = False,
    settings: Settings = Depends(get_settings),
    manager: RuntimeConfigManager = Depends(get_runtime_config_manager),
    store: GlobalAppState = Depends(get_app_state),
    notifier: BroadcastManager = Depends(get_notifier),
) -> MaintenanceCleanupResponse:
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true is required")

    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="cleanup_disabled_in_production")

    config = await manager.get_config()
    if not config.dry_run:
        raise HTTPException(status_code=403, detail="cleanup_requires_dry_run")

    cleaned_at = datetime.now(timezone.utc)

    db_deleted: dict[str, int] = {}
    async with db_session() as session:
        # Trade stats tables
        result = await session.execute(delete(TradeFill))
        db_deleted["trade_fills"] = int(result.rowcount or 0)
        result = await session.execute(delete(HypothesisSession))
        db_deleted["hypothesis_sessions"] = int(result.rowcount or 0)
        result = await session.execute(delete(TradeSession))
        db_deleted["trade_sessions"] = int(result.rowcount or 0)

        # Exchange reconciliation tables
        result = await session.execute(delete(ExchangeTrade))
        db_deleted["exchange_trades"] = int(result.rowcount or 0)
        result = await session.execute(delete(AccountTransaction))
        db_deleted["account_transactions"] = int(result.rowcount or 0)
        result = await session.execute(delete(AccountEquitySnapshot))
        db_deleted["account_equity_snapshots"] = int(result.rowcount or 0)

    redis_keys = [
        EXPERIENCE_KEY,
        FORCE_TRAIN_QUEUE,
        LAST_TRAIN_KEY,
        "rl_metrics:performance",
        "rl_metrics:latest",
        CLOSED_TRADES_KEY,
        "rl_policy:latest",
    ]
    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    try:
        await client.delete(*redis_keys)
    finally:
        await client.aclose()

    # Reset in-memory caches so UI reflects the clean slate immediately.
    await store.reset_for_clean_slate()
    await notifier.broadcast(await store.build_dashboard_state())

    return MaintenanceCleanupResponse(
        status="ok",
        cleaned_at=cleaned_at,
        db_deleted=db_deleted,
        redis_deleted=redis_keys,
    )
