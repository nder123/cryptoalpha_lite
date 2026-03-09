from __future__ import annotations

from typing import Optional

import redis.asyncio as redis

from app.core.config import get_settings


class DecisionRegistry:
    """Persists processed decision identifiers to guarantee idempotency."""

    def __init__(self, ttl_seconds: int = 7 * 24 * 60 * 60) -> None:
        settings = get_settings()
        self._redis = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
        self._ttl_seconds = ttl_seconds

    async def register_if_new(self, decision_uid: Optional[str]) -> bool:
        """Attempt to register the decision; return True if it was unseen."""

        if not decision_uid:
            return False
        key = self._build_key(decision_uid)
        result = await self._redis.set(key, "1", ex=self._ttl_seconds, nx=True)
        return bool(result)

    async def mark_processed(self, decision_uid: Optional[str]) -> None:
        if not decision_uid:
            return
        key = self._build_key(decision_uid)
        await self._redis.set(key, "1", ex=self._ttl_seconds)

    async def close(self) -> None:
        await self._redis.aclose()

    @staticmethod
    def _build_key(decision_uid: str) -> str:
        return f"ctoai:decision:{decision_uid}"
