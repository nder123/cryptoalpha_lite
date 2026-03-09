"""Domain event definitions for message bus communication."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MarketStatus(str, Enum):
    """Market-wide status classification."""

    CALM = "calm"
    NEUTRAL = "neutral"
    VOLATILE = "volatile"
    STRESSED = "stressed"
    UNKNOWN = "unknown"


class SymbolCategory(str, Enum):
    """Symbol categorization within watchlists."""

    IGNORED = "ignored"
    WATCH = "watch"
    CANDIDATE = "candidate"
    ACTIVE = "active"


class MarketSnapshot(BaseModel):
    """Lightweight market metrics emitted by the watcher."""

    symbol: str
    timestamp: datetime
    market_score: float
    status: MarketStatus
    category: SymbolCategory
    rationale: List[str] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }


class HypothesisType(str, Enum):
    TREND = "trend"
    MOMENTUM = "momentum"
    FUNDING_IMBALANCE = "funding_imbalance"
    VOLATILITY_BREAKOUT = "volatility_breakout"
    LIQUIDATION_SWEEP = "liquidation_sweep"
    MEAN_REVERSION = "mean_reversion"


class TradeHypothesis(BaseModel):
    """Research outcome from pair selection engine."""

    hypothesis_id: str
    symbol: str
    created_at: datetime
    hypothesis_type: HypothesisType
    confidence: float
    direction: Literal["long", "short"]
    entry_price: float
    target_price: float
    stop_price: float
    position_size: float
    leverage: float
    notional_usdt: float
    supporting_metrics: Dict[str, float] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)

    model_config = {
        "extra": "forbid",
    }


class RejectedHypothesis(BaseModel):
    """Research rejection payload."""

    hypothesis_id: str
    symbol: str
    created_at: datetime
    reasons: List[str]

    model_config = {
        "extra": "forbid",
    }


class RiskDecision(str, Enum):
    APPROVED = "approved"
    BLOCKED = "blocked"


class RiskAssessment(BaseModel):
    """Risk evaluation result for a trade hypothesis."""

    assessment_id: str
    hypothesis_id: str
    symbol: str
    evaluated_at: datetime
    decision: RiskDecision
    blockers: List[str] = Field(default_factory=list)
    risk_metrics: Dict[str, float] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }


class TradeAction(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    HOLD = "hold"
    REJECT = "reject"
    NO_TRADE = "no_trade"


class TradingMode(str, Enum):
    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"


class TradeDirective(BaseModel):
    """Decision emitted by CTO-AI orchestrator."""

    directive_id: str
    hypothesis_id: Optional[str]
    symbol: str
    issued_at: datetime
    action: TradeAction
    rationale: List[str]
    mode: TradingMode
    confidence: float
    direction: Literal["long", "short"]
    order_type: Literal["market", "limit"]
    quantity: float
    price: Optional[float] = None
    time_in_force: Literal["GTC", "IOC", "FOK"] = "GTC"
    leverage: float
    reduce_only: bool = False
    notional_usdt: float
    expires_at: Optional[datetime] = None
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    decision_uid: Optional[str] = None

    model_config = {
        "extra": "forbid",
    }


class ExecutionStatus(str, Enum):
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"
    FAILED = "failed"
    REJECTED = "rejected"


class PositionEventType(str, Enum):
    """Lifecycle events emitted by the position manager."""

    OPEN_TRACKED = "open_tracked"
    OPEN_UPDATED = "open_updated"
    CLOSE_REQUESTED = "close_requested"
    CLOSE_CONFIRMED = "close_confirmed"
    CLOSE_PARTIAL = "close_partial"
    PRICE_FETCH_FAILED = "price_fetch_failed"
    FORCE_CLOSE_TIMEOUT = "force_close_timeout"
    ERROR = "error"


class PositionEvent(BaseModel):
    """Position manager telemetry event for frontend dashboards."""

    event: PositionEventType
    directive_id: str
    symbol: str
    direction: Literal["long", "short"]
    created_at: datetime
    quantity: float | None = None
    price: float | None = None
    reason: str | None = None
    status: str | None = None
    origin_directive_id: str | None = None
    notes: List[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ExecutionReport(BaseModel):
    """Execution result emitted by the execution engine."""

    directive_id: str
    symbol: str
    action: TradeAction
    status: ExecutionStatus
    quantity: float
    avg_price: Optional[float]
    fees_paid: Optional[float]
    reported_at: datetime
    notes: List[str] = Field(default_factory=list)

    model_config = {
        "extra": "forbid",
    }


class CTOAiDecision(BaseModel):
    """Idempotent execution contract between CTO-AI FSM and ExecutionEngine."""

    decision_uid: str
    directive_id: str
    symbol: str
    issued_at: datetime
    action: TradeAction
    size: float
    notional_usdt: float
    source: Literal["fsm", "operator", "position_manager"]
    meta: Dict[str, Any] = Field(default_factory=dict)
    directive: TradeDirective

    model_config = {
        "extra": "forbid",
    }


class OperatorCommand(BaseModel):
    """Control command issued from the Web Dashboard."""

    command_id: str
    issued_at: datetime
    command_type: Literal["set_mode", "emergency_stop", "manual_decision"]
    payload: Dict[str, str]

    model_config = {
        "extra": "forbid",
    }
