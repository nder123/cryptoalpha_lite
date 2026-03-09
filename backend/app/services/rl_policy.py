from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import redis.asyncio as redis
import torch
import torch.nn as nn

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.rl_state_builder import FEATURE_NAMES

LOGGER = get_logger(__name__)

POLICY_KEY = "rl_policy:latest"
ACTIVE_VERSION_KEY = "rl_policy:active_version"
POLICY_BY_VERSION_PREFIX = "rl_policy:by_version:"


@dataclass(slots=True)
class RLPolicyDecision:
    approved: bool
    score: float
    confidence_multiplier: float
    notional_multiplier: float
    reason: str
    recommended_action: str


@dataclass(slots=True)
class RLPolicy:
    version: str
    weights: List[float]
    bias: float = 0.0
    threshold: float = 0.5
    confidence_scale: float = 0.5
    notional_scale: float = 0.3

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "RLPolicy":
        return cls(
            version=str(payload.get("version", "unknown")),
            weights=[float(value) for value in payload.get("weights", [])],
            bias=float(payload.get("bias", 0.0)),
            threshold=float(payload.get("threshold", 0.5)),
            confidence_scale=float(payload.get("confidence_scale", 0.5)),
            notional_scale=float(payload.get("notional_scale", 0.3)),
        )

    def evaluate(
        self, features: Iterable[float], action: Optional[str]
    ) -> RLPolicyDecision:
        vector = list(features)
        weight_count = len(self.weights)
        if weight_count == 0:
            return RLPolicyDecision(
                True,
                0.0,
                1.0,
                1.0,
                "RL policy fallback (no weights)",
                action or "unknown",
            )

        if len(vector) < weight_count:
            vector.extend([0.0] * (weight_count - len(vector)))
        elif len(vector) > weight_count:
            vector = vector[:weight_count]

        score = (
            sum(weight * value for weight, value in zip(self.weights, vector))
            + self.bias
        )
        probability = 1.0 / (1.0 + math.exp(-score))
        approved = probability >= self.threshold
        delta = probability - self.threshold
        confidence_multiplier = max(0.0, 1.0 + (delta * self.confidence_scale))
        notional_multiplier = max(0.0, 1.0 + (delta * self.notional_scale))
        reason = f"RL policy score={probability:.3f} (threshold {self.threshold:.3f})"
        return RLPolicyDecision(
            approved,
            probability,
            confidence_multiplier,
            notional_multiplier,
            reason,
            action or "unknown",
        )


class ActorCriticNetwork(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, action_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size, hidden_size=hidden_size, batch_first=True
        )
        self.actor = nn.Linear(hidden_size, action_size)
        self.critic = nn.Linear(hidden_size, 1)

    def forward(self, state: torch.Tensor) -> torch.distributions.Categorical:
        # state shape: (batch, seq_len, features)
        out, _ = self.lstm(state)
        last = out[:, -1, :]
        logits = self.actor(last)
        return torch.distributions.Categorical(logits=logits)


class RLPolicyEvaluator:
    def __init__(self) -> None:
        settings = get_settings()
        self._redis = redis.from_url(
            settings.redis_dsn, encoding="utf-8", decode_responses=True
        )
        self._policy: Optional[RLPolicy] = None
        self._policy_version: Optional[str] = None
        self._actor_model: Optional[ActorCriticNetwork] = None
        self._threshold: float = 0.5
        self._confidence_scale: float = 0.5
        self._notional_scale: float = 0.3
        self._state_mean: Optional[torch.Tensor] = None
        self._state_std: Optional[torch.Tensor] = None
        self._action_mapping: Dict[str, int] = {}
        self._inverse_action_mapping: Dict[int, str] = {}
        self._state_dim = len(FEATURE_NAMES)

    def current_policy_version(self) -> Optional[str]:
        return self._policy_version

    async def close(self) -> None:
        await self._redis.aclose()

    async def _load_policy(self) -> Optional[RLPolicy]:
        active_version = await self._redis.get(ACTIVE_VERSION_KEY)
        if active_version:
            raw = await self._redis.get(f"{POLICY_BY_VERSION_PREFIX}{active_version}")
            if raw is None:
                raw = await self._redis.get(POLICY_KEY)
        else:
            raw = await self._redis.get(POLICY_KEY)
        if raw is None:
            LOGGER.debug("rl_policy_missing")
            self._policy = None
            self._policy_version = None
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.warning("rl_policy_invalid_json")
            self._policy = None
            self._policy_version = None
            return None
        version = str(payload.get("version", "unknown"))
        if version == self._policy_version:
            return self._policy

        previous_version = self._policy_version

        architecture = payload.get("architecture")
        if architecture == "lstm_actor_critic":
            try:
                self._setup_actor_policy(payload)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("rl_policy_actor_load_failed", exc_info=exc)
                self._reset_policy()
            return None

        try:
            self._policy = RLPolicy.from_payload(payload)
            self._policy_version = version
            self._threshold = self._policy.threshold
            self._confidence_scale = self._policy.confidence_scale
            self._notional_scale = self._policy.notional_scale
            self._actor_model = None
            self._state_mean = None
            self._state_std = None
            self._action_mapping = {}
            self._inverse_action_mapping = {}
            LOGGER.info(
                "rl_policy_loaded",
                redis_key=POLICY_KEY,
                version=version,
                previous_version=previous_version,
                architecture=payload.get("architecture"),
                threshold=payload.get("threshold"),
            )
            return self._policy
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("rl_policy_parse_failed", exc_info=exc)
            self._reset_policy()
            return None

    def _setup_actor_policy(self, payload: dict[str, object]) -> None:
        input_size = int(payload.get("input_size", self._state_dim))
        hidden_size = int(payload.get("hidden_size", 64))
        action_size = int(payload.get("action_size", 3))
        actor = payload.get("actor")
        critic = payload.get("critic")
        if not isinstance(actor, dict) or not isinstance(critic, dict):
            raise ValueError("actor/critic weights missing")

        if input_size != self._state_dim:
            LOGGER.warning(
                "rl_policy_input_mismatch", expected=self._state_dim, got=input_size
            )
            self._state_dim = input_size

        model = ActorCriticNetwork(input_size, hidden_size, action_size)
        state_dict = model.state_dict()
        lstm = actor.get("lstm")
        linear = actor.get("linear")
        critic_linear = (
            critic.get("linear") if isinstance(critic.get("linear"), dict) else None
        )
        if (
            not isinstance(lstm, dict)
            or not isinstance(linear, dict)
            or critic_linear is None
        ):
            raise ValueError("actor/critic weights malformed")

        state_dict["lstm.weight_ih_l0"] = torch.tensor(
            lstm["weight_ih_l0"], dtype=torch.float32
        )
        state_dict["lstm.weight_hh_l0"] = torch.tensor(
            lstm["weight_hh_l0"], dtype=torch.float32
        )
        state_dict["lstm.bias_ih_l0"] = torch.tensor(
            lstm["bias_ih_l0"], dtype=torch.float32
        )
        state_dict["lstm.bias_hh_l0"] = torch.tensor(
            lstm["bias_hh_l0"], dtype=torch.float32
        )
        state_dict["actor.weight"] = torch.tensor(linear["weight"], dtype=torch.float32)
        state_dict["actor.bias"] = torch.tensor(linear["bias"], dtype=torch.float32)
        state_dict["critic.weight"] = torch.tensor(
            critic_linear["weight"], dtype=torch.float32
        )
        state_dict["critic.bias"] = torch.tensor(
            critic_linear["bias"], dtype=torch.float32
        )
        model.load_state_dict(state_dict)
        model.eval()

        state_norm = payload.get("state_normalization")
        mean = None
        std = None
        if isinstance(state_norm, dict):
            mean = state_norm.get("mean")
            std = state_norm.get("std")
        self._state_mean = (
            torch.tensor(mean, dtype=torch.float32) if isinstance(mean, list) else None
        )
        self._state_std = (
            torch.tensor(std, dtype=torch.float32) if isinstance(std, list) else None
        )

        mapping = payload.get("action_mapping", {})
        if not isinstance(mapping, dict):
            mapping = {}
        self._action_mapping = {str(key): int(value) for key, value in mapping.items()}
        self._inverse_action_mapping = {
            value: key for key, value in self._action_mapping.items()
        }

        self._actor_model = model
        self._policy = None
        self._policy_version = str(payload.get("version", "unknown"))
        self._threshold = float(payload.get("threshold", 0.5))
        self._confidence_scale = float(payload.get("confidence_scale", 0.5))
        self._notional_scale = float(payload.get("notional_scale", 0.3))
        LOGGER.info(
            "rl_policy_loaded",
            redis_key=POLICY_KEY,
            version=self._policy_version,
            architecture="lstm_actor_critic",
            threshold=self._threshold,
        )

    def _reset_policy(self) -> None:
        self._policy = None
        self._actor_model = None
        self._policy_version = None
        self._state_mean = None
        self._state_std = None
        self._action_mapping = {}
        self._inverse_action_mapping = {}
        self._threshold = 0.5
        self._confidence_scale = 0.5
        self._notional_scale = 0.3

    async def evaluate(
        self, features: Iterable[float], action: Optional[str]
    ) -> Optional[RLPolicyDecision]:
        policy = await self._load_policy()
        vector = list(features)
        if self._actor_model is not None:
            return self._evaluate_actor(vector, action)
        if not policy:
            return None
        return policy.evaluate(vector, action)

    async def fetch_state(self, symbol: str) -> Optional[dict[str, object]]:
        raw = await self._redis.get(f"rl_state_cache:{symbol}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.warning("rl_state_invalid_json", symbol=symbol)
            return None

    def _evaluate_actor(
        self, vector: List[float], action: Optional[str]
    ) -> Optional[RLPolicyDecision]:
        if self._actor_model is None:
            return None

        if not self._action_mapping:
            LOGGER.warning("rl_policy_action_mapping_missing")
            return None

        if len(vector) < self._state_dim:
            vector.extend([0.0] * (self._state_dim - len(vector)))
        elif len(vector) > self._state_dim:
            vector = vector[: self._state_dim]

        tensor = torch.tensor(vector, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
        tensor = self._normalize_state(tensor)

        with torch.no_grad():
            dist = self._actor_model(tensor)
            probs = dist.probs.squeeze(0)

        if probs.numel() == 0:
            return None

        best_index = int(torch.argmax(probs).item())
        recommended_action = self._inverse_action_mapping.get(best_index, "unknown")
        action_key = action or recommended_action
        action_index = self._action_mapping.get(action_key)
        if action_index is None:
            action_index = best_index

        score = float(probs[action_index].item())
        delta = score - self._threshold
        approved = action_index == best_index and score >= self._threshold
        confidence_multiplier = max(0.0, 1.0 + (delta * self._confidence_scale))
        notional_multiplier = max(0.0, 1.0 + (delta * self._notional_scale))
        reason = f"RL policy prob={score:.3f}, suggested_action={recommended_action}"
        return RLPolicyDecision(
            approved,
            score,
            confidence_multiplier,
            notional_multiplier,
            reason,
            recommended_action,
        )

    def _normalize_state(self, tensor: torch.Tensor) -> torch.Tensor:
        if self._state_mean is None or self._state_std is None:
            return tensor
        std = torch.where(
            self._state_std < 1e-3, torch.ones_like(self._state_std), self._state_std
        )
        return (tensor - self._state_mean) / std
