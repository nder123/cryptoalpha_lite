"""WebSocket endpoint for real-time dashboard updates."""
from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_notifier_ws
from app.state.notifier import BroadcastManager

ws_router = APIRouter()


@ws_router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket, notifier: BroadcastManager = Depends(get_notifier_ws)) -> None:
    await notifier.connect(websocket)
    try:
        while True:
            # keep connection alive; client side only receives broadcast messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        await notifier.disconnect(websocket)
    except Exception:
        await notifier.disconnect(websocket)
