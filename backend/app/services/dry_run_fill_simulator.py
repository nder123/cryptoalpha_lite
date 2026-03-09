"""Simulate order fills in dry-run mode.

ExecutionEngine emits SUBMITTED reports in dry_run, which prevents downstream components
(trade stats recorder, RL trainer) from seeing FILLED events.

This service listens to execution reports and, when it detects a dry-run SUBMITTED report,
publishes a synthetic FILLED report after a small delay.
"""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.domain import streams
from app.domain.events import (
    ExecutionReport,
    ExecutionStatus,
    TradeAction,
    TradeDirective,
)
from app.exchange.bybit import BybitClient
from app.infrastructure.event_bus import EventBus
from app.state.store import GlobalAppState


@dataclass(slots=True)
class _SymbolMarket:
    mid: float
    updated_at: datetime


class DryRunFillSimulator:
    def __init__(
        self, bus: EventBus, config_manager: RuntimeConfigManager, store: GlobalAppState
    ) -> None:
        self._logger = get_logger(__name__)
        self._bus = bus
        self._config_manager = config_manager
        self._client = BybitClient()
        self._store = store
        self._seen: set[str] = set()
        self._markets: dict[str, _SymbolMarket] = {}

    async def run(self, stop_event: asyncio.Event) -> None:
        group = "dry-run-fill-simulator"
        async for message in self._bus.listen(
            streams.EXECUTION_REPORTS,
            group=group,
            event_type=ExecutionReport,
            stop_event=stop_event,
        ):
            report = message.payload
            try:
                await self._maybe_simulate_fill(report)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "dry_run_fill_simulator_error",
                    directive_id=report.directive_id,
                    error=str(exc),
                )
            finally:
                await self._bus.ack(message.stream, group, message.message_id)
            if stop_event.is_set():
                break

        await self._client.close()

    async def _maybe_simulate_fill(self, report: ExecutionReport) -> None:
        config = await self._config_manager.get_config()
        if not config.dry_run:
            return
        if not getattr(config, "dry_run_fill_simulator_enabled", False):
            return
        if report.status is not ExecutionStatus.SUBMITTED:
            return

        notes = report.notes or []
        if not any("dry-run" in str(note).lower() for note in notes):
            return

        key = f"{report.directive_id}:submitted"
        if key in self._seen:
            return
        self._seen.add(key)

        delay = float(
            getattr(config, "dry_run_fill_simulator_delay_seconds", 0.0) or 0.0
        )
        if delay > 0:
            await asyncio.sleep(delay)

        directive = await self._fetch_directive(report.directive_id)
        fill_price = await self._simulate_fill_price(report, directive)
        fees_paid = self._simulate_fees(
            report.quantity or 0.0,
            fill_price,
            float(getattr(config, "dry_run_fill_simulator_fee_bps", 0.0) or 0.0),
        )

        action = report.action
        if directive is not None:
            action = directive.action

        filled = ExecutionReport(
            directive_id=report.directive_id,
            symbol=report.symbol,
            action=action,
            status=ExecutionStatus.FILLED,
            quantity=report.quantity,
            avg_price=fill_price,
            fees_paid=fees_paid,
            reported_at=datetime.now(timezone.utc),
            notes=[
                *notes,
                "dry-run-fill-simulator=filled",
            ],
        )
        await self._bus.publish(streams.EXECUTION_REPORTS, filled)

    async def _fetch_directive(self, directive_id: str) -> TradeDirective | None:
        try:
            return await self._store.get_directive(directive_id)
        except Exception:  # noqa: BLE001
            return None

    async def _ensure_market(self, symbol: str) -> _SymbolMarket | None:
        now = datetime.now(timezone.utc)
        existing = self._markets.get(symbol)
        if existing is not None:
            return existing

        try:
            ticker = await self._client.get_symbol_ticker(symbol)
        except Exception as exc:  # noqa: BLE001
            self._logger.debug(
                "dry_run_fill_simulator_ticker_failed", symbol=symbol, error=str(exc)
            )
            return None

        base = float(ticker.last_price) if ticker and ticker.last_price else 0.0
        if base <= 0:
            return None

        market = _SymbolMarket(mid=base, updated_at=now)
        self._markets[symbol] = market
        return market

    async def _simulate_fill_price(
        self, report: ExecutionReport, directive: TradeDirective | None
    ) -> float:
        config = await self._config_manager.get_config()
        symbol = str(report.symbol or "").upper()
        now = datetime.now(timezone.utc)

        market = await self._ensure_market(symbol)
        if market is None:
            self._logger.warning("dry_run_fill_simulator_missing_price", symbol=symbol)
            return 0.0

        dt_seconds = max(0.0, (now - market.updated_at).total_seconds())
        if dt_seconds > 0:
            # Drift is specified as bps per minute; volatility as bps (std-dev) per minute.
            drift_bps_per_min = float(
                getattr(config, "dry_run_fill_simulator_drift_bps_per_minute", 0.0)
                or 0.0
            )
            vol_bps = float(
                getattr(config, "dry_run_fill_simulator_volatility_bps", 0.0) or 0.0
            )
            dt_min = dt_seconds / 60.0
            mu = drift_bps_per_min / 10_000.0
            sigma = vol_bps / 10_000.0
            # Simple log-normal step.
            shock = random.gauss(0.0, 1.0)
            market.mid = max(
                0.0001,
                market.mid
                * math.exp(
                    (mu - 0.5 * sigma * sigma) * dt_min
                    + sigma * math.sqrt(max(dt_min, 0.0)) * shock
                ),
            )
            market.updated_at = now

        spread_bps = max(
            0.0, float(getattr(config, "dry_run_fill_simulator_spread_bps", 0.0) or 0.0)
        )
        half_spread = (spread_bps / 10_000.0) / 2.0
        bid = market.mid * (1.0 - half_spread)
        ask = market.mid * (1.0 + half_spread)

        # Determine whether this fill is a buy or sell based on directive action+direction.
        is_buy = True
        if directive is not None:
            if directive.action is TradeAction.OPEN:
                is_buy = directive.direction == "long"
            elif directive.action is TradeAction.CLOSE:
                is_buy = directive.direction == "short"

        base = ask if is_buy else bid

        slippage_bps = max(
            0.0,
            float(getattr(config, "dry_run_fill_simulator_slippage_bps", 0.0) or 0.0),
        )
        slip = slippage_bps / 10_000.0
        # Adverse slippage: buy -> higher, sell -> lower.
        filled = base * (1.0 + slip if is_buy else 1.0 - slip)
        return max(0.0, float(filled))

    @staticmethod
    def _simulate_fees(quantity: float, price: float, fee_bps: float) -> float:
        qty = max(0.0, float(quantity or 0.0))
        px = max(0.0, float(price or 0.0))
        bps = max(0.0, float(fee_bps or 0.0))
        notional = qty * px
        return notional * (bps / 10_000.0)


async def run_dry_run_fill_simulator(
    stop_event: asyncio.Event,
    bus: EventBus,
    config_manager: RuntimeConfigManager,
    store: GlobalAppState,
) -> None:
    simulator = DryRunFillSimulator(bus, config_manager, store)
    await simulator.run(stop_event)
