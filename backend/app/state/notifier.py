"""Simple WebSocket broadcast manager for dashboard updates."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Set

from fastapi import WebSocket


class BroadcastManager:
    """Tracks connected dashboard clients and broadcasts JSON messages."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        data = json.dumps(message, default=str)
        async with self._lock:
            connections = list(self._connections)
        if not connections:
            return
        stale: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_text(data)
            except Exception:  # noqa: BLE001
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.discard(websocket)
