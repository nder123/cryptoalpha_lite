"""Service that keeps the dashboard in sync with Bybit open positions."""

from __future__ import annotations

import asyncio
import json
from typing import Any, List

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.exchange.bybit import BybitClient
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState


class ExchangePositionWatcher:
    """Polls Bybit positions and updates the dashboard state."""

    def __init__(
        self,
        store: GlobalAppState,
        notifier: BroadcastManager,
        config_manager: RuntimeConfigManager,
    ) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._store = store
        self._notifier = notifier
        self._config_manager = config_manager
        self._client = BybitClient()
        self._interval = max(float(self._settings.execution_poll_interval_seconds), 5.0)
        self._last_snapshot: str | None = None
        self._credentials_missing_logged = False
        self._connection_failed_logged = False

    async def run(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                await self._poll_once()
                await asyncio.sleep(self._interval)
        finally:
            await self._client.close()

    async def _poll_once(self) -> None:
        if not self._has_credentials():
            await self._handle_no_credentials()
            return

        try:
            config = await self._config_manager.get_config()
        except Exception as exc:  # noqa: BLE001
            self._logger.exception("position_watcher_config_error", exc_info=exc)
            return

        if config.dry_run:
            metrics = self._calc_metrics([])
            await self._ensure_state([], metrics)
            return

        try:
            positions = await self._client.fetch_positions()
            self._connection_failed_logged = False
        except Exception as exc:  # noqa: BLE001
            try:
                import httpx

                is_connect_error = isinstance(exc, httpx.ConnectError)
            except Exception:  # noqa: BLE001
                is_connect_error = False

            if is_connect_error:
                if not self._connection_failed_logged:
                    self._logger.warning(
                        "position_watcher_bybit_unreachable", error=str(exc)
                    )
                    self._connection_failed_logged = True
                metrics = self._calc_metrics([])
                await self._ensure_state([], metrics)
                return

            self._logger.exception("position_watcher_fetch_failed", exc_info=exc)
            metrics = self._calc_metrics([])
            await self._ensure_state([], metrics)
            return

        metrics = self._calc_metrics(positions)
        await self._ensure_state(positions, metrics)

    def _calc_metrics(self, positions: List[dict[str, Any]]) -> dict[str, Any]:
        total_abs = sum(
            abs(float(position.get("notional_usdt") or 0.0)) for position in positions
        )
        net = sum(
            (float(position.get("notional_usdt") or 0.0))
            * (1 if position.get("side") == "long" else -1)
            for position in positions
        )
        unrealized = sum(
            float(position.get("unrealized_pnl") or 0.0) for position in positions
        )
        from datetime import datetime, timezone

        return {
            "total_abs_exposure": total_abs,
            "net_exposure": net,
            "total_unrealized_pnl": unrealized,
            "positions_count": len(positions),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _ensure_state(
        self, positions: List[dict[str, Any]], metrics: dict[str, Any] | None = None
    ) -> None:
        payload = {"positions": positions, "metrics": metrics}
        fingerprint = json.dumps(payload, sort_keys=True, default=str)
        if fingerprint == self._last_snapshot:
            return

        await self._store.set_positions(positions)
        if metrics is not None:
            await self._store.set_exposure_metrics(metrics)
        await self._notifier.broadcast(await self._store.build_dashboard_state())
        self._last_snapshot = fingerprint

    def _has_credentials(self) -> bool:
        return bool(self._settings.bybit_api_key and self._settings.bybit_api_secret)

    async def _handle_no_credentials(self) -> None:
        if not self._credentials_missing_logged:
            self._logger.warning("position_watcher_disabled_no_credentials")
            self._credentials_missing_logged = True
        metrics = self._calc_metrics([])
        await self._ensure_state([], metrics)


async def run_position_watcher(
    stop_event: asyncio.Event,
    store: GlobalAppState,
    notifier: BroadcastManager,
    config_manager: RuntimeConfigManager,
) -> None:
    watcher = ExchangePositionWatcher(store, notifier, config_manager)
    await watcher.run(stop_event)
