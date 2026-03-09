"""Automatic research manager that keeps the hypothesis pipeline busy."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfig, RuntimeConfigManager
from app.domain import streams
from app.domain.events import MarketSnapshot, MarketStatus, SymbolCategory
from app.infrastructure.event_bus import EventBus
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState

LOGGER = get_logger(__name__)
BACKLOG_KEY = "auto_research:backlog"
SNAPSHOT_HASH = "auto_research:snapshots"
LAST_RUN_HASH = "auto_research:last_run"
HEARTBEAT_SECONDS = 30
COOLDOWN_FRACTION = 0.75  # use fraction of research_refresh_interval for safety


class AutoResearchManager:
    def __init__(
        self,
        bus: EventBus,
        store: GlobalAppState,
        config_manager: RuntimeConfigManager,
        notifier: BroadcastManager | None = None,
    ) -> None:
        self._bus = bus
        self._store = store
        self._config_manager = config_manager
        self._notifier = notifier
        self._settings = get_settings()
        self._redis: redis.Redis[str] = redis.from_url(
            self._settings.redis_dsn,
            encoding="utf-8",
            decode_responses=True,
        )
        self._last_status: str | None = None
        self._last_error: str | None = None

    async def close(self) -> None:
        await self._redis.aclose()

    async def run(self, stop_event: asyncio.Event) -> None:
        LOGGER.info("auto_research_manager_started")
        try:
            while not stop_event.is_set():
                try:
                    await self._tick()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("auto_research_tick_failed", exc_info=exc)
                    await self._update_health("error", error=str(exc))
                try:
                    await asyncio.wait_for(
                        asyncio.shield(stop_event.wait()),
                        timeout=HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:  # pragma: no cover - lifecycle
            raise
        finally:
            await self.close()
            LOGGER.info("auto_research_manager_stopped")

    async def _tick(self) -> None:
        config = await self._config_manager.get_config()
        if not config.auto_research_enabled:
            await self._update_health("paused", message="Auto-research disabled")
            return

        await self._sync_backlog()
        dispatched = await self._dispatch_requests(config)
        backlog_size = await self._redis.zcard(BACKLOG_KEY)
        status = "active" if dispatched else "idle"
        await self._update_health(status, backlog=backlog_size, dispatched=dispatched)

    async def _sync_backlog(self) -> None:
        overview = await self._store.list_market()
        now = datetime.now(timezone.utc)
        updates: dict[str, float] = {}
        snapshot_updates: dict[str, str] = {}

        for symbol, payload in overview.candidate.items():
            score = float(payload.get("score", 0.0) or 0.0)
            info = {
                "score": score,
                "rationale": payload.get("rationale") or [],
                "metrics": payload.get("metrics") or {},
                "timestamp": payload.get("timestamp") or now.isoformat(),
            }
            snapshot_updates[symbol] = json.dumps(info)
            updates[symbol] = score

        if updates:
            await self._redis.zadd(BACKLOG_KEY, updates)
            if snapshot_updates:
                await self._redis.hset(SNAPSHOT_HASH, mapping=snapshot_updates)

    async def _dispatch_requests(self, config: RuntimeConfig) -> int:
        batch_size = max(1, config.auto_research_batch_size)
        now = datetime.now(timezone.utc)
        cooldown_seconds = max(
            30,
            int(config.research_refresh_interval_seconds * COOLDOWN_FRACTION),
        )
        symbols = await self._redis.zrevrange(BACKLOG_KEY, 0, batch_size - 1)
        if not symbols:
            return 0

        dispatched = 0
        for symbol in symbols:
            if dispatched >= batch_size:
                break

            last_run_raw = await self._redis.hget(LAST_RUN_HASH, symbol)
            if last_run_raw:
                try:
                    last_run = datetime.fromisoformat(last_run_raw)
                except ValueError:
                    last_run = None
                if last_run and (now - last_run).total_seconds() < cooldown_seconds:
                    continue

            snapshot_payload = await self._redis.hget(SNAPSHOT_HASH, symbol)
            if not snapshot_payload:
                continue
            try:
                snapshot_data: dict[str, Any] = json.loads(snapshot_payload)
            except json.JSONDecodeError:
                continue

            snapshot = self._build_snapshot(symbol, snapshot_data, now)
            if snapshot is None:
                continue

            await self._bus.publish(streams.MARKET_SNAPSHOTS, snapshot)
            await self._redis.hset(LAST_RUN_HASH, symbol, now.isoformat())
            await self._redis.zadd(BACKLOG_KEY, {symbol: snapshot_data.get("score", 0.0)})
            dispatched += 1

        return dispatched

    def _build_snapshot(
        self,
        symbol: str,
        payload: dict[str, Any],
        fallback_time: datetime,
    ) -> MarketSnapshot | None:
        score = float(payload.get("score", 0.0) or 0.0)
        timestamp_raw = payload.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(timestamp_raw) if timestamp_raw else fallback_time
        except ValueError:
            timestamp = fallback_time

        metrics_raw = payload.get("metrics") or {}
        metrics: dict[str, float] = {}
        for key, value in metrics_raw.items():
            try:
                metrics[key] = float(value)
            except (TypeError, ValueError):
                continue

        rationale_raw = payload.get("rationale") or []
        rationale = [str(item) for item in rationale_raw if isinstance(item, (str, int, float))]

        return MarketSnapshot(
            symbol=symbol,
            timestamp=timestamp,
            market_score=score,
            status=self._derive_status(score),
            category=SymbolCategory.CANDIDATE,
            rationale=rationale,
            metrics=metrics,
        )

    @staticmethod
    def _derive_status(score: float) -> MarketStatus:
        if score >= 75:
            return MarketStatus.VOLATILE
        if score >= 60:
            return MarketStatus.NEUTRAL
        if score >= 40:
            return MarketStatus.CALM
        return MarketStatus.UNKNOWN

    async def _update_health(self, status: str, **details: Any) -> None:
        if status == self._last_status and not details:
            return
        payload: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        payload.update(details)
        await self._store.set_service_health("auto-research-manager", payload)
        if self._notifier is not None:
            await self._notifier.broadcast(await self._store.build_dashboard_state())
        self._last_status = status
        self._last_error = details.get("error") if details else None


async def run_auto_research_manager(
    stop_event: asyncio.Event,
    bus: EventBus,
    store: GlobalAppState,
    config_manager: RuntimeConfigManager,
    notifier: BroadcastManager | None = None,
) -> None:
    manager = AutoResearchManager(bus, store, config_manager, notifier)
    try:
        await manager.run(stop_event)
    finally:
        await manager.close()
