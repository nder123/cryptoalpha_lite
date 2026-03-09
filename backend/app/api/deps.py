"""FastAPI dependency helpers."""

from __future__ import annotations

from typing import cast

from fastapi import Request, WebSocket

from app.core.runtime_config import RuntimeConfigManager
from app.infrastructure.event_bus import EventBus
from app.repositories.runtime_settings import RuntimeSettingsRepository
from app.state.cto_ai import CTOAIOrchestrator
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState


def get_app_state(request: Request) -> GlobalAppState:
    return cast(GlobalAppState, request.app.state.store)


def get_cto_ai(request: Request) -> CTOAIOrchestrator:
    return cast(CTOAIOrchestrator, request.app.state.cto_ai)


def get_notifier(request: Request) -> BroadcastManager:
    return cast(BroadcastManager, request.app.state.notifier)


def get_notifier_ws(websocket: WebSocket) -> BroadcastManager:
    return cast(BroadcastManager, websocket.app.state.notifier)


def get_runtime_config_manager(request: Request) -> RuntimeConfigManager:
    return cast(RuntimeConfigManager, request.app.state.runtime_config_manager)


def get_runtime_settings_repo(request: Request) -> RuntimeSettingsRepository:
    return cast(RuntimeSettingsRepository, request.app.state.runtime_settings_repo)


def get_event_bus(request: Request) -> EventBus:
    return cast(EventBus, request.app.state.event_bus)
