"""Supervisor responsible for running background services."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict

from app.core.logging import get_logger
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState

BackgroundTaskFactory = Callable[[asyncio.Event], Awaitable[None]]


class ServiceSupervisor:
    """Manage lifecycle of background services and expose health state."""

    def __init__(self, store: GlobalAppState | None = None, notifier: BroadcastManager | None = None) -> None:
        self._tasks: Dict[str, asyncio.Task[None]] = {}
        self._stop_event = asyncio.Event()
        self._exit_stack = AsyncExitStack()
        self._logger = get_logger(__name__)
        self._store = store
        self._notifier = notifier

    async def start(self, services: Dict[str, BackgroundTaskFactory]) -> None:
        if self._tasks:
            raise RuntimeError("Supervisor already running")

        for name, factory in services.items():
            self._logger.info("starting_service", service=name)
            await self._record_health(name, status="starting")
            task = asyncio.create_task(self._run_service(name, factory))
            self._tasks[name] = task

    async def _run_service(self, name: str, factory: BackgroundTaskFactory) -> None:
        mark_stopped = True
        try:
            await self._record_health(name, status="running")
            await factory(self._stop_event)
        except asyncio.CancelledError:
            self._logger.info("service_cancelled", service=name)
            raise
        except Exception as exc:  # noqa: BLE001
            error = str(exc) or repr(exc)
            self._logger.exception("service_crashed", service=name, error=error)
            mark_stopped = False
            await self._record_health(name, status="error", error=error)
        finally:
            self._logger.info("service_stopped", service=name)
            if mark_stopped:
                await self._record_health(name, status="stopped")

    async def stop(self) -> None:
        if not self._tasks:
            return

        self._logger.info("supervisor_stop")
        self._stop_event.set()
        for name in list(self._tasks.keys()):
            await self._record_health(name, status="stopping")

        for task in self._tasks.values():
            task.cancel()

        for name, task in list(self._tasks.items()):
            try:
                await task
            except asyncio.CancelledError:
                self._logger.info("service_cancelled", service=name)
            finally:
                self._tasks.pop(name, None)

        await self._exit_stack.aclose()
        self._stop_event = asyncio.Event()

    async def wait_stable(self) -> None:
        await asyncio.sleep(0)

    async def _record_health(self, name: str, /, **payload: object) -> None:
        if self._store is None:
            return
        data: dict[str, object] = {
            "status": payload.get("status", "unknown"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        for key, value in payload.items():
            if key != "status":
                data[key] = value
        await self._store.set_service_health(name, data)
        if self._notifier is not None:
            await self._notifier.broadcast(await self._store.build_dashboard_state())
