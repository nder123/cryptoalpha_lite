"""Background scheduler that triggers RL training when enough experience is accumulated."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.services.rl_trainer import EXPERIENCE_KEY, FORCE_TRAIN_QUEUE

LOGGER = get_logger(__name__)
SCHEDULER_HEARTBEAT_SECONDS = 60


async def run_rl_train_scheduler(
    stop_event: asyncio.Event, config_manager: RuntimeConfigManager
) -> None:
    """Push training requests into the RL trainer force queue."""
    settings = get_settings()
    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    last_trigger: datetime | None = None
    LOGGER.info("rl_train_scheduler_started")
    try:
        while not stop_event.is_set():
            try:
                config = await config_manager.get_config()
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("rl_train_scheduler_config_failed", exc_info=exc)
                await asyncio.sleep(SCHEDULER_HEARTBEAT_SECONDS)
                continue

            if not config.rl_enabled:
                await asyncio.sleep(SCHEDULER_HEARTBEAT_SECONDS)
                continue

            min_batch = max(32, config.rl_retrain_interval_hours * 16)
            interval_seconds = max(int(config.rl_retrain_interval_hours * 3600), 900)

            try:
                experience_count = await client.llen(EXPERIENCE_KEY)
                queue_size = await client.llen(FORCE_TRAIN_QUEUE)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("rl_train_scheduler_redis_failed", exc_info=exc)
                await asyncio.sleep(SCHEDULER_HEARTBEAT_SECONDS)
                continue

            now = datetime.now(timezone.utc)
            should_trigger = (
                queue_size == 0
                and experience_count >= min_batch
                and (
                    last_trigger is None
                    or (now - last_trigger).total_seconds() >= interval_seconds
                )
            )

            if should_trigger:
                payload = {
                    "reason": "scheduler",
                    "priority": "normal",
                    "timestamp": now.isoformat(),
                    "experience_count": experience_count,
                }
                try:
                    await client.rpush(FORCE_TRAIN_QUEUE, json.dumps(payload))
                    last_trigger = now
                    LOGGER.info(
                        "rl_train_scheduler_triggered",
                        request=payload,
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("rl_train_scheduler_trigger_failed", exc_info=exc)

            await asyncio.sleep(SCHEDULER_HEARTBEAT_SECONDS)
    finally:
        await client.aclose()
        LOGGER.info("rl_train_scheduler_stopped")
