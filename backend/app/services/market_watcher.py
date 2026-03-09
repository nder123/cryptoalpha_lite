"""Global market watcher that scans Bybit USDT-M perpetual pairs."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple

import httpx

from app.core.config import get_settings
from app.core.runtime_config import RuntimeConfig, RuntimeConfigManager
from app.core.logging import get_logger
from app.domain.events import MarketSnapshot, MarketStatus, SymbolCategory
from app.domain import streams
from app.exchange.bybit import BybitClient, SymbolTicker
from app.infrastructure.event_bus import EventBus


class GlobalMarketWatcher:
    """Continuously monitors all linear perpetual contracts."""

    def __init__(self, bus: EventBus, config_manager: RuntimeConfigManager) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._bus = bus
        self._client = BybitClient()
        self._config_manager = config_manager
        self._config: RuntimeConfig = RuntimeConfig.from_settings(self._settings)

    async def run(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                self._config = await self._config_manager.get_config()
                sleep_interval = self._config.market_scan_interval_seconds
                try:
                    tickers = await self._client.fetch_tickers()
                    if not tickers:
                        await asyncio.sleep(sleep_interval)
                        continue
                    ranked = self._rank_symbols(tickers, self._config)
                    await self._publish_snapshots(ranked)
                except httpx.RequestError as exc:
                    self._logger.warning("market_watcher_unreachable", error=str(exc))
                    await asyncio.sleep(sleep_interval)
                except Exception:  # noqa: BLE001
                    self._logger.exception("market_watcher_error")
                    await asyncio.sleep(sleep_interval)
                else:
                    await asyncio.sleep(sleep_interval)
        finally:
            await self._client.close()

    async def _publish_snapshots(self, ranked: List[Tuple[str, SymbolTicker, float, SymbolCategory]]) -> None:
        now = datetime.now(timezone.utc)
        ignored = sum(1 for _, _, _, category in ranked if category is SymbolCategory.IGNORED)
        total = max(len(ranked), 1)
        self._logger.debug(
            "market_allocation",
            total=total,
            ignored=ignored,
        )
        for symbol, ticker, score, category in ranked:
            snapshot = MarketSnapshot(
                symbol=symbol,
                timestamp=now,
                market_score=score,
                status=self._derive_status(score),
                category=category,
                rationale=self._build_rationale(ticker),
                metrics=self._baseline_metrics(ticker),
            )
            await self._bus.publish(streams.MARKET_SNAPSHOTS, snapshot)

    def _rank_symbols(
        self,
        tickers: Dict[str, SymbolTicker],
        config: RuntimeConfig,
    ) -> List[Tuple[str, SymbolTicker, float, SymbolCategory]]:
        scored: List[Tuple[str, SymbolTicker, float]] = []
        for symbol, ticker in tickers.items():
            score = self._score_symbol(ticker)
            scored.append((symbol, ticker, score))

        scored.sort(key=lambda item: item[2], reverse=True)
        total = len(scored)
        max_candidates = max(1, config.max_candidate_symbols)
        candidate_limit = min(max_candidates, max(3, int(total * 0.05)))
        watch_limit = min(total, max(candidate_limit + 5, int(total * 0.15)))

        ranked: List[Tuple[str, SymbolTicker, float, SymbolCategory]] = []
        for idx, (symbol, ticker, score) in enumerate(scored):
            if idx < candidate_limit:
                category = SymbolCategory.CANDIDATE
            elif idx < watch_limit:
                category = SymbolCategory.WATCH
            else:
                category = SymbolCategory.IGNORED

            ranked.append((symbol, ticker, score, category))
        return ranked

    def _score_symbol(self, ticker: SymbolTicker) -> float:
        price_component = max(min(ticker.price_24h_pct * 100, 12.0), -12.0)
        funding_component = min(abs(ticker.funding_rate) * 1000, 10.0)
        volume_component = self._log_scale(ticker.turnover_24h)
        open_interest_component = self._log_scale(ticker.open_interest)

        raw_score = 50.0
        raw_score += price_component * 1.5
        raw_score += funding_component * 1.2
        raw_score += volume_component * 1.1
        raw_score += open_interest_component
        raw_score = max(0.0, min(100.0, raw_score))
        return round(raw_score, 2)

    def _derive_status(self, score: float) -> MarketStatus:
        if score >= 75:
            return MarketStatus.VOLATILE
        if score >= 60:
            return MarketStatus.NEUTRAL
        if score >= 40:
            return MarketStatus.CALM
        return MarketStatus.UNKNOWN

    def _baseline_metrics(self, ticker: SymbolTicker) -> Dict[str, float]:
        return {
            "last_price": ticker.last_price,
            "price_24h_pct": ticker.price_24h_pct,
            "funding_rate": ticker.funding_rate,
            "volume_24h": ticker.volume_24h,
            "turnover_24h": ticker.turnover_24h,
            "open_interest": ticker.open_interest,
        }

    def _build_rationale(self, ticker: SymbolTicker) -> List[str]:
        notes: List[str] = []
        if abs(ticker.price_24h_pct) > 0.02:
            notes.append(f"price move {ticker.price_24h_pct*100:.2f}%")
        if abs(ticker.funding_rate) > self._config.funding_threshold:
            notes.append(f"funding {ticker.funding_rate*100:.3f}%")
        if ticker.turnover_24h > 5_000_000:
            notes.append("high turnover")
        if ticker.open_interest > 2_000_000:
            notes.append("rising open interest")
        return notes

    def _log_scale(self, value: float) -> float:
        if value <= 0:
            return 0.0
        return min(12.0, max(0.0, (value ** 0.125)))


async def run_market_watcher(stop_event: asyncio.Event, bus: EventBus, config_manager: RuntimeConfigManager) -> None:
    watcher = GlobalMarketWatcher(bus, config_manager)
    await watcher.run(stop_event)
