"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router
from app.api.websocket import ws_router
from app.core.config import get_settings
from app.core.runtime_config import RuntimeConfigManager
from app.core.logging import configure_logging
from app.domain import streams
from app.domain.events import ExecutionReport, MarketSnapshot, RiskAssessment, TradeHypothesis
from app.infrastructure.database import init_models
from app.infrastructure.event_bus import EventBus, event_bus
from app.services.service_supervisor import ServiceSupervisor
from app.services.market_watcher import run_market_watcher
from app.services.research_engine import run_research_engine
from app.services.risk_engine import run_risk_engine
from app.services.execution_engine import run_execution_engine
from app.services.execution_fill_monitor import run_execution_fill_monitor
from app.services.audit_logger import run_audit_logger
from app.services.auto_exposure_manager import run_auto_exposure_manager
from app.services.auto_research_manager import run_auto_research_manager
from app.services.rl_state_builder import run_rl_state_builder
from app.services.position_manager import run_position_manager
from app.services.position_watcher import run_position_watcher
from app.services.rl_trainer import run_rl_trainer
from app.services.trade_stats_recorder import run_trade_stats_recorder
from app.services.rl_autopilot import run_rl_autopilot
from app.services.dry_run_fill_simulator import run_dry_run_fill_simulator
from app.services.bybit_data_sync import run_bybit_data_sync
from app.services.notification_dispatcher import run_notification_dispatcher
from app.state.cto_ai import CTOAIOrchestrator
from app.state.notifier import BroadcastManager
from app.state.store import GlobalAppState
from app.repositories.event_logs import EventLogRepository
from app.repositories.runtime_settings import RuntimeSettingsRepository
from app.repositories.trade_stats import TradeStatsRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    await init_models()

    runtime_settings_repo = RuntimeSettingsRepository()
    trade_stats_repo = TradeStatsRepository()
    overrides = await runtime_settings_repo.fetch_overrides()
    config_manager = RuntimeConfigManager(settings, overrides)

    app.state.store = GlobalAppState()
    app.state.cto_ai = CTOAIOrchestrator(config_manager, app.state.store)
    app.state.notifier = BroadcastManager()
    app.state.supervisor = ServiceSupervisor(app.state.store, app.state.notifier)
    app.state.runtime_config_manager = config_manager
    app.state.runtime_settings_repo = runtime_settings_repo
    await app.state.store.set_runtime_config(await config_manager.get_config())

    async with event_bus() as bus:
        app.state.event_bus = bus
        services = {
            "market-watcher": lambda stop: run_market_watcher(stop, bus, config_manager),
            "research-engine": lambda stop: run_research_engine(stop, bus, app.state.store, app.state.notifier, config_manager),
            "risk-engine": lambda stop: run_risk_engine(stop, bus, config_manager, app.state.store),
            "execution-engine": lambda stop: run_execution_engine(stop, bus, config_manager, app.state.store),
            "trade-stats-recorder": lambda stop: run_trade_stats_recorder(stop, bus, trade_stats_repo, app.state.store, app.state.notifier),
            "execution-fill-monitor": lambda stop: run_execution_fill_monitor(stop, bus),
            "dry-run-fill-simulator": lambda stop: run_dry_run_fill_simulator(stop, bus, config_manager, app.state.store),
            "position-watcher": lambda stop: run_position_watcher(stop, app.state.store, app.state.notifier, config_manager),
            "position-manager": lambda stop: run_position_manager(stop, bus, app.state.cto_ai, app.state.store, app.state.notifier, config_manager),
            "audit-logger": lambda stop: run_audit_logger(stop, bus, EventLogRepository()),
            "auto-exposure-manager": lambda stop: run_auto_exposure_manager(stop, config_manager, runtime_settings_repo, app.state.store, app.state.notifier),
            "auto-research-manager": lambda stop: run_auto_research_manager(stop, bus, app.state.store, config_manager, app.state.notifier),
            "notification-dispatcher": lambda stop: run_notification_dispatcher(stop, config_manager),
            "rl-state-builder": lambda stop: run_rl_state_builder(stop, bus, config_manager, trade_stats_repo),
            "rl-trainer": lambda stop: run_rl_trainer(stop, bus, config_manager, trade_stats_repo),
            "rl-autopilot": lambda stop: run_rl_autopilot(stop, bus, config_manager, trade_stats_repo, app.state.cto_ai, app.state.store, app.state.notifier),
            "bybit-data-sync": lambda stop: run_bybit_data_sync(stop, config_manager),
            "ctoai-market-listener": lambda stop: ctoai_market_listener(stop, app.state.cto_ai, app.state.store, app.state.notifier, bus),
            "ctoai-hypothesis-listener": lambda stop: ctoai_hypothesis_listener(stop, app.state.cto_ai, app.state.store, app.state.notifier, bus),
            "ctoai-risk-listener": lambda stop: ctoai_risk_listener(stop, app.state.cto_ai, app.state.store, app.state.notifier, bus),
            "ctoai-execution-listener": lambda stop: ctoai_execution_listener(stop, app.state.cto_ai, app.state.store, app.state.notifier, bus),
        }
        await app.state.supervisor.start(services)
        try:
            yield
        finally:
            await app.state.supervisor.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="CTO-AI Backend", lifespan=lifespan)
    app.include_router(router, prefix="/api")
    app.include_router(ws_router)
    return app


app = create_app()


async def ctoai_market_listener(
    stop: asyncio.Event,
    orchestrator: CTOAIOrchestrator,
    store: GlobalAppState,
    notifier: BroadcastManager,
    bus: EventBus,
) -> None:
    async for message in bus.listen(
        streams.MARKET_SNAPSHOTS,
        group="ctoai",
        event_type=MarketSnapshot,
        stop_event=stop,
    ):
        await orchestrator.handle_market_snapshot(message.payload)
        await store.update_market(message.payload)
        await store.set_ctoai_snapshot(await orchestrator.snapshot())
        await notifier.broadcast(await store.build_dashboard_state())
        await bus.ack(message.stream, "ctoai", message.message_id)
        if stop.is_set():
            break


async def ctoai_hypothesis_listener(
    stop: asyncio.Event,
    orchestrator: CTOAIOrchestrator,
    store: GlobalAppState,
    notifier: BroadcastManager,
    bus: EventBus,
) -> None:
    async for message in bus.listen(
        streams.RESEARCH_HYPOTHESES,
        group="ctoai",
        event_type=TradeHypothesis,
        stop_event=stop,
    ):
        await orchestrator.handle_hypothesis(message.payload)
        await store.set_ctoai_snapshot(await orchestrator.snapshot())
        await notifier.broadcast(await store.build_dashboard_state())
        await bus.ack(message.stream, "ctoai", message.message_id)
        if stop.is_set():
            break


async def ctoai_risk_listener(
    stop: asyncio.Event,
    orchestrator: CTOAIOrchestrator,
    store: GlobalAppState,
    notifier: BroadcastManager,
    bus: EventBus,
) -> None:
    async for message in bus.listen(
        streams.RISK_ASSESSMENTS,
        group="ctoai",
        event_type=RiskAssessment,
        stop_event=stop,
    ):
        directive = await orchestrator.handle_risk_assessment(message.payload)
        await bus.ack(message.stream, "ctoai", message.message_id)
        if directive:
            decision = orchestrator.build_decision(directive, source="fsm")
            await store.upsert_directive(directive)
            await bus.publish(streams.CTOAI_DIRECTIVES, directive)
            await bus.publish(streams.CTOAI_DECISIONS, decision)
        await store.set_ctoai_snapshot(await orchestrator.snapshot())
        await notifier.broadcast(await store.build_dashboard_state())
        if stop.is_set():
            break


async def ctoai_execution_listener(
    stop: asyncio.Event,
    orchestrator: CTOAIOrchestrator,
    store: GlobalAppState,
    notifier: BroadcastManager,
    bus: EventBus,
) -> None:
    async for message in bus.listen(
        streams.EXECUTION_REPORTS,
        group="ctoai",
        event_type=ExecutionReport,
        stop_event=stop,
    ):
        await orchestrator.handle_execution_report(message.payload)
        remove_directive = message.payload.status.name in {"FILLED", "FAILED", "CANCELLED"}
        if not remove_directive and message.payload.status.name == "SUBMITTED":
            try:
                runtime_config = await store.get_runtime_config()
            except Exception:
                runtime_config = {}
            is_dry_run = bool(runtime_config.get("dry_run"))
            notes = message.payload.notes or []
            if is_dry_run and any("dry-run" in str(note).lower() for note in notes):
                remove_directive = True

        if remove_directive:
            await store.remove_directive(message.payload.directive_id)
        await store.set_ctoai_snapshot(await orchestrator.snapshot())
        await notifier.broadcast(await store.build_dashboard_state())
        await bus.ack(message.stream, "ctoai", message.message_id)
        if stop.is_set():
            break
