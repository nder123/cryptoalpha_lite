from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List, Optional

import redis.asyncio as redis
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfig, RuntimeConfigManager
from app.domain import streams
from app.domain.events import (
    ExecutionReport,
    ExecutionStatus,
    TradeAction,
    TradeDirective,
)
from app.infrastructure.event_bus import EventBus, EventMessage
from app.repositories.trade_stats import TradeStatsRepository
from app.services.rl_state_builder import FEATURE_NAMES

LOGGER = get_logger(__name__)
POLICY_KEY = "rl_policy:latest"
ACTIVE_VERSION_KEY = "rl_policy:active_version"
POLICY_BY_VERSION_PREFIX = "rl_policy:by_version:"
EXPERIENCE_KEY = "rl_trainer:experience_buffer"
FORCE_TRAIN_QUEUE = "rl_trainer:force_requests"
LAST_TRAIN_KEY = "rl_trainer:last_train_at"
DIRECTIVE_GROUP = "rl-trainer-directives"
EXECUTION_GROUP = "rl-trainer-execution"
CONFIG_REFRESH_SECONDS = 60
TRAIN_HEARTBEAT_SECONDS = 10
MAX_PENDING = 2048
PERFORMANCE_KEY = "rl_metrics:performance"
LATEST_METRICS_KEY = "rl_metrics:latest"
CLOSED_TRADES_KEY = "rl_metrics:closed_trades"


@dataclass(slots=True)
class PendingExperience:
    directive_id: str
    directive: TradeDirective
    state: List[float]
    action_index: int
    created_at: datetime


@dataclass(slots=True)
class Experience:
    directive_id: str
    symbol: str
    action: str
    state: List[float]
    action_index: int
    reward: float
    log_prob: float
    value: float
    timestamp: datetime


@dataclass(slots=True)
class PerformanceSnapshot:
    total_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_window: float
    losses_last_window: int
    loss_window_size: int


class PerformanceTracker:
    def __init__(
        self,
        redis_client: redis.Redis[str],
        key: str,
        window: int = 200,
        loss_window: int = 50,
    ) -> None:
        self._redis = redis_client
        self._key = key
        self._window = window
        self._loss_window = loss_window
        self._returns: Deque[float] = deque(maxlen=window)
        self._loss_tracker: Deque[float] = deque(maxlen=loss_window)
        self._total_trades = 0
        self._wins = 0
        self._equity_curve: List[float] = []
        self._equity = 0.0
        self._equity_peak = 0.0
        self._max_drawdown = 0.0

    async def load(self) -> None:
        raw = await self._redis.get(self._key)
        if raw is None:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        self._returns = deque(payload.get("returns", []), maxlen=self._window)
        self._loss_tracker = deque(
            payload.get("loss_tracker", []), maxlen=self._loss_window
        )
        self._total_trades = int(payload.get("total_trades", 0))
        self._wins = int(payload.get("wins", 0))
        self._equity = float(payload.get("equity", 0.0))
        self._equity_peak = float(payload.get("equity_peak", 0.0))
        self._max_drawdown = float(payload.get("max_drawdown", 0.0))
        self._equity_curve = payload.get("equity_curve", [])[-self._window :]

    async def persist(self) -> None:
        payload = {
            "returns": list(self._returns),
            "loss_tracker": list(self._loss_tracker),
            "total_trades": self._total_trades,
            "wins": self._wins,
            "equity": self._equity,
            "equity_peak": self._equity_peak,
            "max_drawdown": self._max_drawdown,
            "equity_curve": self._equity_curve[-self._window :],
        }
        await self._redis.set(self._key, json.dumps(payload))

    def update(self, pnl_frac: float) -> PerformanceSnapshot:
        """Update rolling performance statistics.

        pnl_frac is the fractional PnL per trade:
        - 0.01 == +1%
        - 1.0 == +100%
        """
        self._total_trades += 1
        if pnl_frac > 0:
            self._wins += 1
        self._returns.append(pnl_frac)
        self._loss_tracker.append(pnl_frac)
        self._equity += pnl_frac
        self._equity_peak = max(self._equity_peak, self._equity)
        drawdown = self._equity - self._equity_peak
        self._max_drawdown = min(self._max_drawdown, drawdown)
        self._equity_curve.append(self._equity)

        window_max_drawdown = self._compute_window_max_drawdown()

        win_rate = self._wins / self._total_trades if self._total_trades else 0.0
        sharpe = self._compute_sharpe()
        losses_last_window = sum(1 for value in self._loss_tracker if value <= 0)
        loss_window_size = len(self._loss_tracker)

        return PerformanceSnapshot(
            total_trades=self._total_trades,
            win_rate=win_rate,
            sharpe_ratio=sharpe,
            max_drawdown=self._max_drawdown,
            max_drawdown_window=window_max_drawdown,
            losses_last_window=losses_last_window,
            loss_window_size=loss_window_size,
        )

    def _compute_window_max_drawdown(self) -> float:
        if not self._equity_curve:
            return 0.0
        window = self._equity_curve[-self._window :]
        peak = window[0]
        max_dd = 0.0
        for value in window:
            peak = max(peak, value)
            max_dd = min(max_dd, value - peak)
        return max_dd

    def _compute_sharpe(self) -> float:
        if not self._returns:
            return 0.0
        returns = [value / 100.0 for value in self._returns]
        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / max(
            len(returns) - 1, 1
        )
        std_dev = variance**0.5
        if std_dev < 1e-6:
            return 0.0
        # Annualize using sqrt of trades to approximate Sharpe per trade
        return (mean_return / std_dev) * (len(returns) ** 0.5)


class RunningStats:
    def __init__(self, size: int) -> None:
        self.size = size
        self.count = 0
        self.mean = torch.zeros(size)
        self.m2 = torch.zeros(size)

    def update(self, values: List[float]) -> None:
        tensor = torch.tensor(values, dtype=torch.float32)
        self.count += 1
        delta = tensor - self.mean
        self.mean += delta / self.count
        delta2 = tensor - self.mean
        self.m2 += delta * delta2

    def serialize(self) -> dict[str, object]:
        std = self.std()
        return {
            "count": self.count,
            "mean": self.mean.tolist(),
            "std": std.tolist(),
        }

    def load(self, payload: dict[str, object]) -> None:
        self.count = int(payload.get("count", 0))
        mean = payload.get("mean")
        std = payload.get("std")
        if isinstance(mean, list) and len(mean) == self.size:
            self.mean = torch.tensor(mean, dtype=torch.float32)
        if isinstance(std, list) and len(std) == self.size:
            computed_m2 = torch.tensor(std, dtype=torch.float32) ** 2 * max(
                self.count - 1, 1
            )
            self.m2 = computed_m2

    def std(self) -> torch.Tensor:
        if self.count < 2:
            return torch.ones_like(self.mean)
        return torch.sqrt(self.m2 / max(self.count - 1, 1))


class ActorCriticNetwork(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, action_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size, hidden_size=hidden_size, batch_first=True
        )
        self.actor = nn.Linear(hidden_size, action_size)
        self.critic = nn.Linear(hidden_size, 1)

    def forward(
        self, state: torch.Tensor
    ) -> tuple[torch.distributions.Categorical, torch.Tensor]:
        # state shape: (batch, seq_len, features)
        out, _ = self.lstm(state)
        last = out[:, -1, :]
        logits = self.actor(last)
        value = self.critic(last)
        dist = torch.distributions.Categorical(logits=logits)
        return dist, value.squeeze(-1)


class RLTrainer:
    def __init__(
        self,
        bus: EventBus,
        config_manager: RuntimeConfigManager,
        stats_repo: TradeStatsRepository,
    ) -> None:
        self._bus = bus
        self._config_manager = config_manager
        self._settings = get_settings()
        self._redis: redis.Redis[str] = redis.from_url(
            self._settings.redis_dsn, encoding="utf-8", decode_responses=True
        )
        LOGGER.info("rl_trainer_redis_config", redis_dsn=self._settings.redis_dsn)
        self._state_dim = len(FEATURE_NAMES)
        self._action_mapping: Dict[str, int] = {"reject": 0, "open": 1, "close": 2}
        self._inverse_action_mapping = {
            value: key for key, value in self._action_mapping.items()
        }
        self._action_dim = len(self._action_mapping)
        self._hidden_size = 64
        self._policy = ActorCriticNetwork(
            self._state_dim, self._hidden_size, self._action_dim
        )
        self._optimizer = optim.Adam(self._policy.parameters(), lr=3e-4)
        self._config: RuntimeConfig | None = None
        self._pending: Dict[str, PendingExperience] = {}
        self._buffer: List[Experience] = []
        self._running_stats = RunningStats(self._state_dim)
        self._stats_repo = stats_repo
        self._performance_tracker = PerformanceTracker(self._redis, PERFORMANCE_KEY)
        self._train_interval = timedelta(hours=6)
        self._experience_window = timedelta(days=30)
        self._ppo_epochs = 4
        self._ppo_clip = 0.2
        self._value_coef = 0.5
        self._entropy_coef = 0.01
        self._min_batch = 64
        self._experience_max = 5000
        self._last_train_at: datetime | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        LOGGER.info("rl_trainer_started")
        try:
            info = await self._redis.info("server")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("rl_trainer_redis_info_failed", error=str(exc))
        else:
            LOGGER.info(
                "rl_trainer_redis_server",
                run_id=info.get("run_id"),
                redis_version=info.get("redis_version"),
            )
        self._config = await self._config_manager.get_config()
        self._apply_config(self._config)
        await self._load_existing_policy()
        await self._performance_tracker.load()
        await self._load_experience_buffer()
        raw_last_train = await self._redis.get(LAST_TRAIN_KEY)
        if raw_last_train:
            try:
                self._last_train_at = datetime.fromisoformat(raw_last_train)
            except ValueError:
                LOGGER.warning(
                    "rl_trainer_last_train_timestamp_invalid", value=raw_last_train
                )
        tasks = [
            asyncio.create_task(self._consume_directives(stop_event)),
            asyncio.create_task(self._consume_executions(stop_event)),
            asyncio.create_task(self._config_loop(stop_event)),
            asyncio.create_task(self._training_loop(stop_event)),
        ]
        try:
            await stop_event.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self._redis.aclose()
            LOGGER.info("rl_trainer_stopped")

    async def _config_loop(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                await asyncio.sleep(CONFIG_REFRESH_SECONDS)
                try:
                    config = await self._config_manager.get_config()
                    self._apply_config(config)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("rl_trainer_config_failed", exc_info=exc)
        except asyncio.CancelledError:
            raise

    async def _training_loop(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                await asyncio.sleep(TRAIN_HEARTBEAT_SECONDS)
                if not self._config or not self._config.rl_enabled:
                    continue

                buffer_size = len(self._buffer)
                force_queue_size = await self._redis.llen(FORCE_TRAIN_QUEUE)

                if buffer_size < self._min_batch:
                    if force_queue_size:
                        LOGGER.warning(
                            "rl_trainer_force_skipped_insufficient_buffer",
                            pending=buffer_size,
                            required=self._min_batch,
                            queue=force_queue_size,
                        )
                    continue

                force_request: dict[str, object] | None = None
                if force_queue_size:
                    raw_request = await self._redis.lpop(FORCE_TRAIN_QUEUE)
                    if raw_request:
                        try:
                            force_request = json.loads(raw_request)
                        except json.JSONDecodeError:
                            force_request = {"raw": raw_request}

                if not force_request:
                    now = datetime.now(timezone.utc)
                    if (
                        self._last_train_at
                        and now - self._last_train_at < self._train_interval
                    ):
                        continue
                    oldest = min(exp.timestamp for exp in self._buffer)
                    if now - oldest < self._train_interval:
                        continue

                await self._train_policy()
                self._last_train_at = datetime.now(timezone.utc)
                try:
                    await self._redis.set(
                        LAST_TRAIN_KEY, self._last_train_at.isoformat()
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception(
                        "rl_trainer_last_train_persist_failed", exc_info=exc
                    )
                if force_request is not None:
                    LOGGER.info(
                        "rl_trainer_forced_training_completed", request=force_request
                    )
        except asyncio.CancelledError:
            raise

    async def _consume_directives(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.CTOAI_DIRECTIVES,
            group=DIRECTIVE_GROUP,
            event_type=TradeDirective,
            stop_event=stop_event,
        ):
            await self._handle_directive(message)

    async def _consume_executions(self, stop_event: asyncio.Event) -> None:
        async for message in self._bus.listen(
            streams.EXECUTION_REPORTS,
            group=EXECUTION_GROUP,
            event_type=ExecutionReport,
            stop_event=stop_event,
        ):
            await self._handle_execution(message)

    async def _handle_directive(self, message: EventMessage[TradeDirective]) -> None:
        directive = message.payload
        if not self._config or not self._config.rl_enabled:
            return
        if len(self._pending) >= MAX_PENDING:
            LOGGER.warning(
                "rl_trainer_pending_overflow", directive_id=directive.directive_id
            )
            await self._bus.ack(message.stream, DIRECTIVE_GROUP, message.message_id)
            return
        action_index = self._action_mapping.get(directive.action.value, 0)
        state_vector = await self._fetch_state_vector(directive.symbol)
        if state_vector is None:
            LOGGER.debug("rl_trainer_state_missing", symbol=directive.symbol)
            return
        pending = PendingExperience(
            directive_id=directive.directive_id,
            directive=directive,
            state=state_vector,
            action_index=action_index,
            created_at=datetime.now(timezone.utc),
        )
        self._pending[directive.directive_id] = pending
        await self._bus.ack(message.stream, DIRECTIVE_GROUP, message.message_id)

    async def _handle_execution(self, message: EventMessage[ExecutionReport]) -> None:
        report = message.payload
        await self._bus.ack(message.stream, EXECUTION_GROUP, message.message_id)
        pending = self._pending.get(report.directive_id)
        if not pending:
            LOGGER.info(
                "rl_trainer_execution_without_pending",
                directive_id=report.directive_id,
                symbol=report.symbol,
                action=(
                    report.action.value
                    if hasattr(report.action, "value")
                    else report.action
                ),
                status=(
                    report.status.value
                    if hasattr(report.status, "value")
                    else report.status
                ),
            )
            return
        reward = await self._compute_reward(pending.directive, report)
        if reward is None:
            return
        self._pending.pop(report.directive_id, None)
        await self._finalize_experience(pending, reward)

    async def _finalize_experience(
        self, pending: PendingExperience, reward: float
    ) -> None:
        self._running_stats.update(pending.state)
        state_tensor = (
            torch.tensor(pending.state, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
        )
        state_tensor = self._normalize_state(state_tensor)
        with torch.no_grad():
            dist, value = self._policy(state_tensor)
            log_prob = dist.log_prob(torch.tensor([pending.action_index]))
        experience = Experience(
            directive_id=pending.directive_id,
            symbol=pending.directive.symbol,
            action=pending.directive.action.value,
            state=pending.state,
            action_index=pending.action_index,
            reward=reward,
            log_prob=log_prob.item(),
            value=value.item(),
            timestamp=datetime.now(timezone.utc),
        )
        self._buffer.append(experience)
        await self._persist_experience_record(experience)
        self._trim_buffer()

    async def _train_policy(self) -> None:
        LOGGER.info("rl_trainer_training_started", samples=len(self._buffer))
        states = torch.tensor([exp.state for exp in self._buffer], dtype=torch.float32)
        actions = torch.tensor(
            [exp.action_index for exp in self._buffer], dtype=torch.long
        )
        rewards = torch.tensor(
            [exp.reward for exp in self._buffer], dtype=torch.float32
        )
        old_log_probs = torch.tensor(
            [exp.log_prob for exp in self._buffer], dtype=torch.float32
        )
        values = torch.tensor([exp.value for exp in self._buffer], dtype=torch.float32)

        normalized_states = self._normalize_state(states.unsqueeze(1))
        returns = rewards
        advantages = returns - values
        if advantages.std().item() > 1e-8:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        for _ in range(self._ppo_epochs):
            dist, new_values = self._policy(normalized_states)
            log_probs = dist.log_prob(actions)
            ratios = torch.exp(log_probs - old_log_probs)
            surr1 = ratios * advantages
            surr2 = (
                torch.clamp(ratios, 1.0 - self._ppo_clip, 1.0 + self._ppo_clip)
                * advantages
            )
            actor_loss = -torch.min(surr1, surr2).mean()
            value_loss = F.mse_loss(new_values, returns)
            entropy = dist.entropy().mean()
            loss = (
                actor_loss
                + self._value_coef * value_loss
                - self._entropy_coef * entropy
            )

            self._optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self._policy.parameters(), max_norm=0.5)
            self._optimizer.step()

        await self._persist_policy()
        LOGGER.info("rl_trainer_training_completed", samples=len(self._buffer))

    def _normalize_state(self, tensor: torch.Tensor) -> torch.Tensor:
        std = self._running_stats.std()
        std = torch.where(std < 1e-3, torch.ones_like(std), std)
        return (tensor - self._running_stats.mean) / std

    def _trim_buffer(self) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now - self._experience_window
        self._buffer = [exp for exp in self._buffer if exp.timestamp >= cutoff]
        if len(self._buffer) > 10_000:
            self._buffer = self._buffer[-10_000:]

    async def _fetch_state_vector(self, symbol: str) -> Optional[List[float]]:
        key = f"rl_state_cache:{symbol}"
        payload_raw = await self._redis.get(key)
        if not payload_raw:
            return None
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            LOGGER.warning("rl_trainer_state_corrupt", symbol=symbol)
            return None
        vector = payload.get("vector")
        if isinstance(vector, list):
            return [float(value) for value in vector]
        return None

    async def _persist_experience_record(self, experience: Experience) -> None:
        payload = {
            "directive_id": experience.directive_id,
            "symbol": experience.symbol,
            "action": experience.action,
            "state": experience.state,
            "action_index": experience.action_index,
            "reward": experience.reward,
            "log_prob": experience.log_prob,
            "value": experience.value,
            "timestamp": experience.timestamp.isoformat(),
        }
        try:
            serialized = json.dumps(payload)
        except (TypeError, ValueError) as exc:  # noqa: BLE001
            LOGGER.exception("rl_trainer_experience_serialize_failed", exc_info=exc)
            return
        try:
            pipe = self._redis.pipeline()
            pipe.rpush(EXPERIENCE_KEY, serialized)
            pipe.ltrim(EXPERIENCE_KEY, -self._experience_max, -1)
            await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("rl_trainer_experience_persist_failed", exc_info=exc)

    async def _load_experience_buffer(self) -> None:
        try:
            raw_items = await self._redis.lrange(
                EXPERIENCE_KEY, -self._experience_max, -1
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("rl_trainer_experience_load_failed", exc_info=exc)
            return
        if not raw_items:
            return
        restored: List[Experience] = []
        for raw in raw_items:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                LOGGER.warning("rl_trainer_experience_invalid_json")
                continue
            state = payload.get("state")
            if not isinstance(state, list):
                continue
            try:
                experience = Experience(
                    directive_id=str(payload.get("directive_id", "")),
                    symbol=str(payload.get("symbol", "")),
                    action=str(payload.get("action", "")),
                    state=[float(value) for value in state],
                    action_index=int(payload.get("action_index", 0)),
                    reward=float(payload.get("reward", 0.0)),
                    log_prob=float(payload.get("log_prob", 0.0)),
                    value=float(payload.get("value", 0.0)),
                    timestamp=datetime.fromisoformat(payload.get("timestamp")),
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("rl_trainer_experience_restore_failed", exc_info=exc)
                continue
            restored.append(experience)
            self._running_stats.update(experience.state)
        if restored:
            self._buffer.extend(restored)

    async def _compute_reward(
        self, directive: TradeDirective, report: ExecutionReport
    ) -> Optional[float]:
        status = report.status
        if status in {
            ExecutionStatus.CANCELLED,
            ExecutionStatus.FAILED,
            ExecutionStatus.REJECTED,
        }:
            return -1.0

        if status == ExecutionStatus.PARTIALLY_FILLED:
            return 0.2

        if status != ExecutionStatus.FILLED:
            return None

        if directive.action == TradeAction.OPEN:
            # Small positive reinforcement for successful entry; main reward comes at exit
            return 0.1

        if directive.action != TradeAction.CLOSE:
            return None

        session: Optional[dict[str, object]] = None
        matched = None
        attempts = 0
        # Trade stats may lag behind execution reports by a short moment; retry a few times.
        for delay in (0.0, 0.25, 0.5, 1.0, 2.0):
            attempts += 1
            if delay:
                await asyncio.sleep(delay)
            try:
                matched = await self._stats_repo.get_session_by_exit_directive_id(
                    directive.directive_id
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception(
                    "rl_reward_session_lookup_failed",
                    exc_info=exc,
                    directive_id=directive.directive_id,
                    attempt=attempts,
                )
                matched = None
                break
            if matched is not None:
                break

        if matched is not None:
            session = {
                "session_id": matched.session_id,
                "symbol": matched.symbol,
                "direction": matched.direction,
                "opened_at": (
                    matched.opened_at.isoformat() if matched.opened_at else None
                ),
                "closed_at": (
                    matched.closed_at.isoformat() if matched.closed_at else None
                ),
                "entry_directive_id": matched.entry_directive_id,
                "exit_directive_id": matched.exit_directive_id,
                "pnl_usdt": (
                    float(matched.pnl_usdt) if matched.pnl_usdt is not None else None
                ),
                "pnl_pct": (
                    float(matched.pnl_pct) if matched.pnl_pct is not None else None
                ),
                "duration_seconds": matched.duration_seconds,
            }
        else:
            sessions = await self._stats_repo.list_sessions(
                symbol=directive.symbol, limit=10
            )
            items = sessions.get("items", []) if sessions else []
            if not items:
                LOGGER.warning(
                    "rl_reward_session_missing",
                    directive_id=directive.directive_id,
                    symbol=directive.symbol,
                )
                return None

            for candidate in items:
                if (
                    isinstance(candidate, dict)
                    and candidate.get("exit_directive_id") == directive.directive_id
                ):
                    session = candidate
                    break

            if session is None:
                LOGGER.warning(
                    "rl_reward_session_mismatch",
                    directive_id=directive.directive_id,
                    symbol=directive.symbol,
                    lookup_attempts=attempts,
                    recent_exit_ids=[
                        item.get("exit_directive_id")
                        for item in items
                        if isinstance(item, dict) and item.get("exit_directive_id")
                    ],
                )
                return None

        pnl_frac_raw = float(session.get("pnl_pct") or 0.0)
        pnl_usdt = float(session.get("pnl_usdt") or 0.0)

        if abs(pnl_frac_raw) > 1.0:
            LOGGER.warning(
                "rl_reward_pnl_frac_outlier",
                directive_id=directive.directive_id,
                status=str(status),
                session_id=session.get("session_id"),
                symbol=session.get("symbol"),
                duration_seconds=session.get("duration_seconds"),
                pnl_usdt=pnl_usdt,
                pnl_frac_raw=pnl_frac_raw,
            )

        # NOTE: Trade stats may contain occasional outliers or unit mismatches.
        # We clip the value used for reward shaping and performance tracking to
        # keep the training signal stable.
        pnl_frac_used = max(min(pnl_frac_raw, 0.3), -0.3)
        reward = pnl_frac_used / 2.0

        await self._record_closed_trade(session)
        snapshot = self._performance_tracker.update(pnl_frac_used)
        await self._performance_tracker.persist()

        if pnl_frac_used >= 5.0:
            reward += 1.0
        if snapshot.win_rate >= 0.6 and snapshot.total_trades >= 5:
            reward += 0.5
        if snapshot.sharpe_ratio >= 1.5 and snapshot.total_trades >= 10:
            reward += 0.5

        if pnl_frac_used <= -2.0:
            reward -= 0.5
        if snapshot.max_drawdown_window <= -10.0:
            reward -= 2.0
        if pnl_frac_used <= 0.0 and snapshot.total_trades >= 20:
            loss_window_size = max(1, int(snapshot.loss_window_size))
            loss_rate = float(snapshot.losses_last_window) / float(loss_window_size)
            if loss_rate > 0.60:
                reward -= min((loss_rate - 0.60) * 0.5, 0.10)

        # Encourage capital efficiency: penalize trivial returns relative to exposure
        if abs(pnl_usdt) < 1.0 and pnl_frac_used == 0.0:
            reward -= 0.1

        # Clamp to avoid extreme gradients
        reward = max(min(reward, 5.0), -5.0)

        await self._publish_metrics(snapshot, pnl_frac_raw, pnl_frac_used, reward)
        return reward

    async def _record_closed_trade(self, session: dict[str, object]) -> None:
        payload = {
            "session_id": session.get("session_id"),
            "symbol": session.get("symbol"),
            "direction": session.get("direction"),
            "opened_at": session.get("opened_at"),
            "closed_at": session.get("closed_at"),
            "entry_directive_id": session.get("entry_directive_id"),
            "exit_directive_id": session.get("exit_directive_id"),
            "pnl_usdt": session.get("pnl_usdt"),
            "pnl_pct": session.get("pnl_pct"),
            "duration_seconds": session.get("duration_seconds"),
        }
        try:
            await self._redis.lpush(CLOSED_TRADES_KEY, json.dumps(payload))
            await self._redis.ltrim(CLOSED_TRADES_KEY, 0, 49)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("rl_closed_trade_record_failed", exc_info=exc)

    def _apply_config(self, config: RuntimeConfig) -> None:
        self._config = config
        self._train_interval = timedelta(hours=config.rl_retrain_interval_hours)
        self._experience_window = timedelta(days=config.rl_experience_window_days)
        self._min_batch = max(32, config.rl_retrain_interval_hours * 16)

    async def _persist_policy(self) -> None:
        state_dict = self._policy.state_dict()
        payload = {
            "version": datetime.now(timezone.utc).isoformat(),
            "architecture": "lstm_actor_critic",
            "threshold": self._config.rl_policy_min_confidence if self._config else 0.7,
            "confidence_scale": 0.5,
            "notional_scale": 0.3,
            "input_size": self._state_dim,
            "hidden_size": self._hidden_size,
            "action_size": self._action_dim,
            "action_mapping": self._action_mapping,
            "state_normalization": self._running_stats.serialize(),
            "actor": {
                "lstm": {
                    "weight_ih_l0": state_dict["lstm.weight_ih_l0"].tolist(),
                    "weight_hh_l0": state_dict["lstm.weight_hh_l0"].tolist(),
                    "bias_ih_l0": state_dict["lstm.bias_ih_l0"].tolist(),
                    "bias_hh_l0": state_dict["lstm.bias_hh_l0"].tolist(),
                },
                "linear": {
                    "weight": state_dict["actor.weight"].tolist(),
                    "bias": state_dict["actor.bias"].tolist(),
                },
            },
            "critic": {
                "linear": {
                    "weight": state_dict["critic.weight"].tolist(),
                    "bias": state_dict["critic.bias"].tolist(),
                }
            },
        }

        version = str(payload.get("version"))
        await self._redis.set(
            f"{POLICY_BY_VERSION_PREFIX}{version}", json.dumps(payload)
        )
        await self._redis.set(POLICY_KEY, json.dumps(payload))
        await self._redis.set(ACTIVE_VERSION_KEY, version, nx=True)
        LOGGER.info(
            "rl_trainer_policy_persisted",
            version=version,
            redis_key=POLICY_KEY,
            architecture=payload.get("architecture"),
            input_size=payload.get("input_size"),
            hidden_size=payload.get("hidden_size"),
            action_size=payload.get("action_size"),
            threshold=payload.get("threshold"),
        )

    async def _load_existing_policy(self) -> None:
        raw = await self._redis.get(POLICY_KEY)
        if not raw:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.warning("rl_trainer_policy_invalid_json")
            return
        if payload.get("architecture") != "lstm_actor_critic":
            LOGGER.info(
                "rl_trainer_policy_arch_mismatch",
                architecture=payload.get("architecture"),
            )
            return
        try:
            self._load_network_weights(payload)
            state_norm = payload.get("state_normalization")
            if isinstance(state_norm, dict):
                self._running_stats.load(state_norm)
            LOGGER.info(
                "rl_trainer_policy_loaded",
                version=payload.get("version"),
                redis_key=POLICY_KEY,
                architecture=payload.get("architecture"),
                input_size=payload.get("input_size"),
                hidden_size=payload.get("hidden_size"),
                action_size=payload.get("action_size"),
                threshold=payload.get("threshold"),
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("rl_trainer_policy_load_failed", exc_info=exc)

    def _load_network_weights(self, payload: dict[str, object]) -> None:
        actor = payload.get("actor")
        if not isinstance(actor, dict):
            raise ValueError("actor weights missing")
        lstm_weights = actor.get("lstm")
        linear_weights = actor.get("linear")
        critic = payload.get("critic")
        if (
            not isinstance(lstm_weights, dict)
            or not isinstance(linear_weights, dict)
            or not isinstance(critic, dict)
        ):
            raise ValueError("actor/critic weights malformed")

        state_dict = self._policy.state_dict()
        state_dict["lstm.weight_ih_l0"] = torch.tensor(
            lstm_weights["weight_ih_l0"], dtype=torch.float32
        )
        state_dict["lstm.weight_hh_l0"] = torch.tensor(
            lstm_weights["weight_hh_l0"], dtype=torch.float32
        )
        state_dict["lstm.bias_ih_l0"] = torch.tensor(
            lstm_weights["bias_ih_l0"], dtype=torch.float32
        )
        state_dict["lstm.bias_hh_l0"] = torch.tensor(
            lstm_weights["bias_hh_l0"], dtype=torch.float32
        )
        state_dict["actor.weight"] = torch.tensor(
            linear_weights["weight"], dtype=torch.float32
        )
        state_dict["actor.bias"] = torch.tensor(
            linear_weights["bias"], dtype=torch.float32
        )
        critic_linear = critic.get("linear")
        if not isinstance(critic_linear, dict):
            raise ValueError("critic weights missing")
        state_dict["critic.weight"] = torch.tensor(
            critic_linear["weight"], dtype=torch.float32
        )
        state_dict["critic.bias"] = torch.tensor(
            critic_linear["bias"], dtype=torch.float32
        )
        self._policy.load_state_dict(state_dict)

    async def _publish_metrics(
        self,
        snapshot: PerformanceSnapshot,
        pnl_frac_raw: float,
        pnl_frac_used: float,
        reward: float,
    ) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_trades": snapshot.total_trades,
            "win_rate": snapshot.win_rate,
            "sharpe_ratio": snapshot.sharpe_ratio,
            "max_drawdown": snapshot.max_drawdown,
            "max_drawdown_window": snapshot.max_drawdown_window,
            "losses_last_window": snapshot.losses_last_window,
            "loss_window_size": snapshot.loss_window_size,
            "last_trade_pnl_pct": pnl_frac_raw,
            "last_trade_pnl_pct_used": pnl_frac_used,
            "last_trade_reward": reward,
        }
        try:
            await self._redis.set(LATEST_METRICS_KEY, json.dumps(payload))
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("rl_metrics_publish_failed", exc_info=exc)
        else:
            LOGGER.info(
                "rl_performance_update",
                total_trades=snapshot.total_trades,
                win_rate=round(snapshot.win_rate, 4),
                sharpe=round(snapshot.sharpe_ratio, 4),
                max_drawdown=round(snapshot.max_drawdown, 4),
                max_drawdown_window=round(snapshot.max_drawdown_window, 4),
                last_pnl_frac=round(pnl_frac_raw, 4),
                last_pnl_frac_used=round(pnl_frac_used, 4),
                reward=round(reward, 4),
            )


async def run_rl_trainer(
    stop_event: asyncio.Event,
    bus: EventBus,
    config_manager: RuntimeConfigManager,
    stats_repo: TradeStatsRepository,
) -> None:
    trainer = RLTrainer(bus, config_manager, stats_repo)
    try:
        await trainer.run(stop_event)
    finally:
        LOGGER.info("rl_trainer_shutdown")
