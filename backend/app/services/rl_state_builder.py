"""Background service collecting RL state features for symbols."""

from __future__ import annotations

import asyncio
import json
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any, Dict, List

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfig, RuntimeConfigManager
from app.domain import streams
from app.domain.events import (ExecutionReport, ExecutionStatus,
                               MarketSnapshot, RiskAssessment, RiskDecision,
                               TradeDirective, TradeHypothesis)
from app.infrastructure.event_bus import EventBus, EventMessage
from app.repositories.trade_stats import TradeStatsRepository

LOGGER = get_logger(__name__)
STATE_KEY_PREFIX = "rl_state_cache"
STATE_TTL_SECONDS = 3600
PORTFOLIO_REFRESH_SECONDS = 300
CONFIG_REFRESH_SECONDS = 30
GROUP_NAME = "rl-state-builder"
FEATURE_NAMES: List[str] = [
    "market_score",
    "market_status",
    "price_change_5m",
    "price_change_15m",
    "price_change_1h",
    "volume_ratio",
    "volatility",
    "ema_fast_pct",
    "ema_slow_pct",
    "ema_trend",
    "ema_crossover_up",
    "ema_crossover_down",
    "rsi",
    "rsi_low_frequency",
    "rsi_high_frequency",
    "hyp_confidence",
    "hyp_expected_rr",
    "hyp_leverage",
    "hyp_notional_usdt",
    "hyp_direction",
    "risk_approved",
    "risk_blockers",
    "portfolio_win_rate",
    "portfolio_avg_pnl_pct",
    "portfolio_profit_factor",
    "portfolio_avg_rr",
    "portfolio_trades",
    "action_1",
    "action_2",
    "action_3",
    "action_4",
    "action_5",
    "reward_1",
    "reward_2",
    "reward_3",
    "reward_4",
    "reward_5",
]

MARKET_STATUS_ENCODE = {
    "calm": -1.0,
    "neutral": 0.0,
    "volatile": 1.0,
    "stressed": 2.0,
    "unknown": 0.0,
}
DIRECTION_ENCODE = {"long": 1.0, "short": -1.0}
ACTION_ENCODE = {
    "open": 1.0,
    "close": -1.0,
    "hold": 0.5,
    "reject": -0.5,
    "no_trade": 0.0,
}
EXECUTION_STATUS_ENCODE = {
    ExecutionStatus.SUBMITTED: 0.2,
    ExecutionStatus.PARTIALLY_FILLED: 0.6,
    ExecutionStatus.FILLED: 1.0,
    ExecutionStatus.CANCELLED: -0.5,
    ExecutionStatus.FAILED: -1.0,
    ExecutionStatus.REJECTED: -1.0,
}

EMA_FAST_PERIOD_MINUTES = 5.0
EMA_SLOW_PERIOD_MINUTES = 15.0
RSI_PERIOD_MINUTES = 70.0  # 14 periods on 5m candles
RSI_FREQ_WINDOW = 50
MIN_TIME_STEP_MINUTES = 1.0 / 12.0  # ~5 seconds safeguard


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class SymbolState:
    symbol: str
    market: Dict[str, Any] = field(default_factory=dict)
    hypothesis: Dict[str, Any] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    portfolio: Dict[str, Any] = field(default_factory=dict)
    recent_actions: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    recent_rewards: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    last_update: datetime | None = None
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    ema_fast_pct: float = 0.0
    ema_slow_pct: float = 0.0
    ema_trend: float = 0.0
    ema_crossover_up: float = 0.0
    ema_crossover_down: float = 0.0
    rsi_value: float = 50.0
    rsi_low_frequency: float = 0.0
    rsi_high_frequency: float = 0.0
    _avg_gain: float = 0.0
    _avg_loss: float = 0.0
    _last_price: float | None = None
    _last_timestamp: datetime | None = None
    _rsi_hits_low: deque[int] = field(
        default_factory=lambda: deque(maxlen=RSI_FREQ_WINDOW)
    )
    _rsi_hits_high: deque[int] = field(
        default_factory=lambda: deque(maxlen=RSI_FREQ_WINDOW)
    )

    def update_market(self, snapshot: MarketSnapshot) -> None:
        metrics = snapshot.metrics or {}
        status_code = MARKET_STATUS_ENCODE.get(snapshot.status.value, 0.0)
        self.market = {
            "timestamp": snapshot.timestamp.isoformat(),
            "market_score": _safe_float(snapshot.market_score),
            "status": snapshot.status.value,
            "status_code": status_code,
            "category": snapshot.category.value,
            "metrics": metrics,
        }
        price = _safe_float(metrics.get("last_price"), 0.0)
        if price > 0:
            self._update_indicators(snapshot.timestamp, price)

    def update_hypothesis(self, hypothesis: TradeHypothesis) -> None:
        rr = 0.0
        entry = _safe_float(hypothesis.entry_price, 0.0)
        target = _safe_float(hypothesis.target_price, 0.0)
        stop = _safe_float(hypothesis.stop_price, 0.0)
        if entry and stop and entry != stop:
            if hypothesis.direction == "long":
                rr = (target - entry) / (entry - stop) if entry - stop != 0 else 0.0
            else:
                rr = (entry - target) / (stop - entry) if stop - entry != 0 else 0.0
        self.hypothesis = {
            "hypothesis_id": hypothesis.hypothesis_id,
            "created_at": hypothesis.created_at.isoformat(),
            "confidence": _safe_float(hypothesis.confidence),
            "direction": hypothesis.direction,
            "direction_code": DIRECTION_ENCODE.get(hypothesis.direction, 0.0),
            "entry_price": entry,
            "target_price": target,
            "stop_price": stop,
            "expected_rr": rr,
            "leverage": _safe_float(hypothesis.leverage),
            "notional_usdt": _safe_float(hypothesis.notional_usdt),
        }

    def record_directive(self, directive: TradeDirective) -> None:
        self.recent_actions.append(ACTION_ENCODE.get(directive.action.value, 0.0))
        self.execution["last_directive"] = {
            "directive_id": directive.directive_id,
            "issued_at": directive.issued_at.isoformat(),
            "mode": directive.mode.value,
            "confidence": _safe_float(directive.confidence),
            "notional_usdt": _safe_float(directive.notional_usdt),
        }
        # In case hypothesis info missing (manual directives)
        if directive.hypothesis_id is None and directive.symbol == self.symbol:
            self.hypothesis.update(
                {
                    "confidence": _safe_float(directive.confidence),
                    "direction": directive.direction,
                    "direction_code": DIRECTION_ENCODE.get(directive.direction, 0.0),
                    "notional_usdt": _safe_float(directive.notional_usdt),
                    "leverage": _safe_float(directive.leverage),
                }
            )

    def update_risk(self, assessment: RiskAssessment) -> None:
        approved = 1.0 if assessment.decision == RiskDecision.APPROVED else 0.0
        self.risk = {
            "assessment_id": assessment.assessment_id,
            "evaluated_at": assessment.evaluated_at.isoformat(),
            "decision": assessment.decision.value,
            "approved_prob": approved,
            "blockers": assessment.blockers,
            "blocker_count": len(assessment.blockers),
            "risk_metrics": assessment.risk_metrics,
        }

    def record_execution(self, report: ExecutionReport) -> None:
        status_value = EXECUTION_STATUS_ENCODE.get(report.status, 0.0)
        self.execution.update(
            {
                "last_execution": {
                    "directive_id": report.directive_id,
                    "status": report.status.value,
                    "status_score": status_value,
                    "quantity": _safe_float(report.quantity),
                    "avg_price": _safe_float(report.avg_price),
                    "fees_paid": _safe_float(report.fees_paid),
                    "reported_at": report.reported_at.isoformat(),
                }
            }
        )

    def update_portfolio(self, metrics: Dict[str, Any]) -> None:
        self.portfolio = metrics
        rewards = metrics.get("recent_pnls", [])
        self.recent_rewards.clear()
        for value in rewards:
            self.recent_rewards.append(_safe_float(value))

    def to_vector(self) -> List[float]:
        market_metrics = self.market.get("metrics", {}) if self.market else {}
        price = _safe_float(market_metrics.get("last_price", 0.0))
        features: List[float] = [
            _safe_float(self.market.get("market_score") if self.market else 0.0),
            _safe_float(self.market.get("status_code") if self.market else 0.0),
            _safe_float(market_metrics.get("price_change_5m", 0.0)),
            _safe_float(market_metrics.get("price_change_15m", 0.0)),
            _safe_float(market_metrics.get("price_change_1h", 0.0)),
            _safe_float(market_metrics.get("volume_ratio", 0.0)),
            _safe_float(market_metrics.get("volatility", 0.0)),
            self.ema_fast_pct if price else self.ema_fast_pct,
            self.ema_slow_pct if price else self.ema_slow_pct,
            self.ema_trend,
            self.ema_crossover_up,
            self.ema_crossover_down,
            self.rsi_value,
            self.rsi_low_frequency,
            self.rsi_high_frequency,
            _safe_float(self.hypothesis.get("confidence") if self.hypothesis else 0.0),
            _safe_float(self.hypothesis.get("expected_rr") if self.hypothesis else 0.0),
            _safe_float(self.hypothesis.get("leverage") if self.hypothesis else 0.0),
            _safe_float(
                self.hypothesis.get("notional_usdt") if self.hypothesis else 0.0
            ),
            _safe_float(
                self.hypothesis.get("direction_code") if self.hypothesis else 0.0
            ),
            _safe_float(self.risk.get("approved_prob") if self.risk else 0.0),
            _safe_float(self.risk.get("blocker_count") if self.risk else 0.0),
            _safe_float(self.portfolio.get("win_rate") if self.portfolio else 0.0),
            _safe_float(self.portfolio.get("avg_pnl_pct") if self.portfolio else 0.0),
            _safe_float(self.portfolio.get("profit_factor") if self.portfolio else 0.0),
            _safe_float(self.portfolio.get("avg_rr") if self.portfolio else 0.0),
            _safe_float(self.portfolio.get("trades_count") if self.portfolio else 0.0),
        ]
        actions = list(self.recent_actions)
        while len(actions) < 5:
            actions.append(0.0)
        rewards = list(self.recent_rewards)
        while len(rewards) < 5:
            rewards.append(0.0)
        features.extend(actions[:5])
        features.extend(rewards[:5])
        return features

    def to_payload(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "features": {
                "market": self.market,
                "hypothesis": self.hypothesis,
                "risk": self.risk,
                "execution": self.execution,
                "portfolio": self.portfolio,
                "indicators": {
                    "ema_fast": self.ema_fast,
                    "ema_slow": self.ema_slow,
                    "ema_fast_pct": self.ema_fast_pct,
                    "ema_slow_pct": self.ema_slow_pct,
                    "ema_trend": self.ema_trend,
                    "ema_crossover_up": self.ema_crossover_up,
                    "ema_crossover_down": self.ema_crossover_down,
                    "rsi": self.rsi_value,
                    "rsi_low_frequency": self.rsi_low_frequency,
                    "rsi_high_frequency": self.rsi_high_frequency,
                },
            },
            "vector": self.to_vector(),
            "feature_names": FEATURE_NAMES,
        }

    def _update_indicators(self, timestamp: datetime, price: float) -> None:
        if price <= 0:
            return

        prev_fast = self.ema_fast
        prev_slow = self.ema_slow
        last_price = self._last_price if self._last_price is not None else price
        last_timestamp = (
            self._last_timestamp if self._last_timestamp is not None else timestamp
        )
        delta_minutes = max(
            (timestamp - last_timestamp).total_seconds() / 60.0, MIN_TIME_STEP_MINUTES
        )

        alpha_fast = 1 - math.exp(-delta_minutes / EMA_FAST_PERIOD_MINUTES)
        alpha_slow = 1 - math.exp(-delta_minutes / EMA_SLOW_PERIOD_MINUTES)

        if self._last_price is None:
            self.ema_fast = price
            self.ema_slow = price
            self._avg_gain = 0.0
            self._avg_loss = 0.0
        else:
            self.ema_fast = (price * alpha_fast) + (self.ema_fast * (1 - alpha_fast))
            self.ema_slow = (price * alpha_slow) + (self.ema_slow * (1 - alpha_slow))

        change = price - last_price
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        alpha_rsi = 1 - math.exp(-delta_minutes / RSI_PERIOD_MINUTES)

        if self._last_price is None:
            self._avg_gain = gain
            self._avg_loss = loss
        else:
            self._avg_gain = (gain * alpha_rsi) + (self._avg_gain * (1 - alpha_rsi))
            self._avg_loss = (loss * alpha_rsi) + (self._avg_loss * (1 - alpha_rsi))

        if self._avg_loss == 0:
            self.rsi_value = 100.0 if self._avg_gain > 0 else 50.0
        else:
            rs = self._avg_gain / self._avg_loss
            self.rsi_value = 100.0 - (100.0 / (1.0 + rs))

        if self._avg_gain == 0 and self._avg_loss == 0:
            self.rsi_value = 50.0

        self._rsi_hits_low.append(1 if self.rsi_value < 30.0 else 0)
        self._rsi_hits_high.append(1 if self.rsi_value > 70.0 else 0)

        if self._rsi_hits_low:
            self.rsi_low_frequency = sum(self._rsi_hits_low) / len(self._rsi_hits_low)
        else:
            self.rsi_low_frequency = 0.0

        if self._rsi_hits_high:
            self.rsi_high_frequency = sum(self._rsi_hits_high) / len(
                self._rsi_hits_high
            )
        else:
            self.rsi_high_frequency = 0.0

        crossover_up = (
            1.0 if prev_fast <= prev_slow and self.ema_fast > self.ema_slow else 0.0
        )
        crossover_down = (
            1.0 if prev_fast >= prev_slow and self.ema_fast < self.ema_slow else 0.0
        )
        self.ema_crossover_up = crossover_up
        self.ema_crossover_down = crossover_down

        self.ema_fast_pct = (self.ema_fast - price) / price if price else 0.0
        self.ema_slow_pct = (self.ema_slow - price) / price if price else 0.0
        self.ema_trend = (self.ema_fast - self.ema_slow) / price if price else 0.0

        self._last_price = price
        self._last_timestamp = timestamp


class RLStateBuilder:
    def __init__(
        self,
        bus: EventBus,
        redis_client: redis.Redis[Any],
        config_manager: RuntimeConfigManager,
        stats_repo: TradeStatsRepository,
    ) -> None:
        self._bus = bus
        self._redis = redis_client
        self._config_manager = config_manager
        self._stats_repo = stats_repo
        self._states: Dict[str, SymbolState] = {}
        self._portfolio_refresh: Dict[str, datetime] = {}
        self._config: RuntimeConfig | None = None
        self._lock = asyncio.Lock()

    async def run(self, stop_event: asyncio.Event) -> None:
        LOGGER.info("rl_state_builder_started")
        self._config = await self._config_manager.get_config()
        tasks = [
            asyncio.create_task(self._consume_market(stop_event)),
            asyncio.create_task(self._consume_hypotheses(stop_event)),
            asyncio.create_task(self._consume_risk(stop_event)),
            asyncio.create_task(self._consume_directives(stop_event)),
            asyncio.create_task(self._consume_executions(stop_event)),
            asyncio.create_task(self._refresh_loop(stop_event)),
        ]
        try:
            await stop_event.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            LOGGER.info("rl_state_builder_stopped")

    async def _consume_market(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.MARKET_SNAPSHOTS,
            GROUP_NAME,
            MarketSnapshot,
            stop_event=stop_event,
        ):
            await self._handle_market(message)

    async def _consume_hypotheses(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.RESEARCH_HYPOTHESES,
            GROUP_NAME,
            TradeHypothesis,
            stop_event=stop_event,
        ):
            await self._handle_hypothesis(message)

    async def _consume_risk(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.RISK_ASSESSMENTS,
            GROUP_NAME,
            RiskAssessment,
            stop_event=stop_event,
        ):
            await self._handle_risk(message)

    async def _consume_directives(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.CTOAI_DIRECTIVES,
            GROUP_NAME,
            TradeDirective,
            stop_event=stop_event,
        ):
            await self._handle_directive(message)

    async def _consume_executions(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.EXECUTION_REPORTS,
            GROUP_NAME,
            ExecutionReport,
            stop_event=stop_event,
        ):
            await self._handle_execution(message)

    async def _refresh_loop(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                await asyncio.sleep(CONFIG_REFRESH_SECONDS)
                try:
                    self._config = await self._config_manager.get_config()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception(
                        "rl_state_builder_config_refresh_failed", exc_info=exc
                    )
                await self._refresh_portfolio_metrics()
        except asyncio.CancelledError:
            raise

    async def _handle_market(self, message: EventMessage[MarketSnapshot]) -> None:
        snapshot = message.payload
        state = self._get_state(snapshot.symbol)
        state.update_market(snapshot)
        await self._persist_state(snapshot.symbol)
        await self._bus.ack(message.stream, GROUP_NAME, message.message_id)

    async def _handle_hypothesis(self, message: EventMessage[TradeHypothesis]) -> None:
        hypothesis = message.payload
        state = self._get_state(hypothesis.symbol)
        state.update_hypothesis(hypothesis)
        await self._persist_state(hypothesis.symbol)
        await self._bus.ack(message.stream, GROUP_NAME, message.message_id)

    async def _handle_risk(self, message: EventMessage[RiskAssessment]) -> None:
        assessment = message.payload
        state = self._get_state(assessment.symbol)
        state.update_risk(assessment)
        await self._persist_state(assessment.symbol)
        await self._bus.ack(message.stream, GROUP_NAME, message.message_id)

    async def _handle_directive(self, message: EventMessage[TradeDirective]) -> None:
        directive = message.payload
        state = self._get_state(directive.symbol)
        state.record_directive(directive)
        await self._persist_state(directive.symbol)
        await self._bus.ack(message.stream, GROUP_NAME, message.message_id)

    async def _handle_execution(self, message: EventMessage[ExecutionReport]) -> None:
        report = message.payload
        state = self._get_state(report.symbol)
        state.record_execution(report)
        await self._persist_state(report.symbol)
        await self._bus.ack(message.stream, GROUP_NAME, message.message_id)

    def _get_state(self, symbol: str) -> SymbolState:
        if symbol not in self._states:
            self._states[symbol] = SymbolState(symbol=symbol)
        return self._states[symbol]

    async def _refresh_portfolio_metrics(self) -> None:
        now = datetime.now(timezone.utc)
        tasks = []
        for symbol in list(self._states.keys()):
            last_refresh = self._portfolio_refresh.get(symbol)
            if last_refresh and (now - last_refresh) < timedelta(
                seconds=PORTFOLIO_REFRESH_SECONDS
            ):
                continue
            tasks.append(self._update_portfolio(symbol))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _update_portfolio(self, symbol: str) -> None:
        try:
            result = await self._stats_repo.list_sessions(symbol=symbol, limit=50)
            items = result.get("items", [])
            closed = [item for item in items if item.get("pnl_usdt") is not None]
            if not closed:
                metrics = {
                    "win_rate": 0.0,
                    "avg_pnl_pct": 0.0,
                    "profit_factor": 0.0,
                    "avg_rr": 0.0,
                    "trades_count": 0,
                    "recent_pnls": [],
                }
            else:
                pnls = [_safe_float(item.get("pnl_usdt"), 0.0) for item in closed]
                pnl_pct = [_safe_float(item.get("pnl_pct"), 0.0) for item in closed]
                rr_values = [
                    _safe_float(item.get("risk_reward_ratio"), 0.0)
                    for item in closed
                    if item.get("risk_reward_ratio") is not None
                ]
                wins = [value for value in pnls if value > 0]
                losses = [-value for value in pnls if value < 0]
                profit_factor = (
                    sum(wins) / sum(losses) if losses else (sum(wins) if wins else 0.0)
                )
                metrics = {
                    "win_rate": len(wins) / len(closed),
                    "avg_pnl_pct": fmean(pnl_pct) if pnl_pct else 0.0,
                    "profit_factor": profit_factor,
                    "avg_rr": fmean(rr_values) if rr_values else 0.0,
                    "trades_count": len(closed),
                    "recent_pnls": pnls[:5],
                }
            state = self._get_state(symbol)
            state.update_portfolio(metrics)
            await self._persist_state(symbol)
            self._portfolio_refresh[symbol] = datetime.now(timezone.utc)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "rl_state_builder_portfolio_refresh_failed",
                extra={"symbol": symbol},
                exc_info=exc,
            )

    async def _persist_state(self, symbol: str) -> None:
        async with self._lock:
            state = self._get_state(symbol)
            payload = state.to_payload()
            state.last_update = datetime.now(timezone.utc)
            key = f"{STATE_KEY_PREFIX}:{symbol}"
            await self._redis.set(key, json.dumps(payload), ex=STATE_TTL_SECONDS)


async def run_rl_state_builder(
    stop_event: asyncio.Event,
    bus: EventBus,
    config_manager: RuntimeConfigManager,
    stats_repo: TradeStatsRepository,
) -> None:
    settings = get_settings()
    redis_client = redis.from_url(
        settings.redis_dsn, encoding="utf-8", decode_responses=True
    )
    builder = RLStateBuilder(bus, redis_client, config_manager, stats_repo)
    try:
        await builder.run(stop_event)
    finally:
        await redis_client.aclose()
