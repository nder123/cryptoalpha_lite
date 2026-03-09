"""In-memory application state cache shared across API and services."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.domain.events import MarketSnapshot, RejectedHypothesis, SymbolCategory, TradeDirective


@dataclass(slots=True)
class MarketOverview:
    ignored: Dict[str, dict] = field(default_factory=dict)
    watch: Dict[str, dict] = field(default_factory=dict)
    candidate: Dict[str, dict] = field(default_factory=dict)
    active: Dict[str, dict] = field(default_factory=dict)


class GlobalAppState:
    """Thread-safe holder for dashboard data."""

    def __init__(self) -> None:
        self._market = MarketOverview()
        self._ctoai_snapshot: dict[str, object] = {
            "mode": "manual",
            "state": "idle",
            "confidence": 0.0,
            "active_directives": [],
        }
        self._directives: Dict[str, TradeDirective] = {}
        self._rejections: List[dict[str, object]] = []
        self._positions: List[dict[str, object]] = []
        self._runtime_config: dict[str, Any] = {}
        self._exposure_metrics: dict[str, Any] = {
            "total_abs_exposure": 0.0,
            "net_exposure": 0.0,
            "total_unrealized_pnl": 0.0,
            "positions_count": 0,
            "updated_at": None,
        }
        self._risk_budget: dict[str, Any] = {
            "portfolio_limit": 0.0,
            "total_equity": 0.0,
            "available_equity": 0.0,
            "symbol_limits": {},
            "updated_at": None,
        }
        self._trade_stats_overview: dict[str, Any] = {
            "summary": None,
            "recent": [],
            "last_trade": None,
            "updated_at": None,
        }
        self._service_health: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def update_market(self, snapshot: MarketSnapshot) -> None:
        async with self._lock:
            buckets = {
                SymbolCategory.IGNORED: self._market.ignored,
                SymbolCategory.WATCH: self._market.watch,
                SymbolCategory.CANDIDATE: self._market.candidate,
                SymbolCategory.ACTIVE: self._market.active,
            }
            for bucket in buckets.values():
                bucket.pop(snapshot.symbol, None)
            buckets[snapshot.category][snapshot.symbol] = {
                "score": snapshot.market_score,
                "rationale": snapshot.rationale,
                "metrics": snapshot.metrics,
                "timestamp": snapshot.timestamp.isoformat(),
            }

    async def list_market(self) -> MarketOverview:
        async with self._lock:
            return MarketOverview(
                ignored=dict(self._market.ignored),
                watch=dict(self._market.watch),
                candidate=dict(self._market.candidate),
                active=dict(self._market.active),
            )

    async def record_rejection(self, rejection: RejectedHypothesis) -> None:
        async with self._lock:
            self._rejections.append(
                {
                    "hypothesis_id": rejection.hypothesis_id,
                    "symbol": rejection.symbol,
                    "created_at": rejection.created_at.isoformat(),
                    "reasons": rejection.reasons,
                }
            )
            if len(self._rejections) > 200:
                self._rejections = self._rejections[-200:]

    async def list_rejections(self) -> List[dict[str, object]]:
        async with self._lock:
            return list(self._rejections)

    async def clear_rejections(self) -> int:
        async with self._lock:
            cleared = len(self._rejections)
            self._rejections.clear()
            return cleared

    async def set_runtime_config(self, config: "RuntimeConfig" | dict[str, Any]) -> None:
        data: dict[str, Any]
        if hasattr(config, "model_dump"):
            data = config.model_dump()
        else:
            data = dict(config)
        updated_at = data.get("updated_at")
        if isinstance(updated_at, datetime):
            data["updated_at"] = updated_at.isoformat()
        async with self._lock:
            self._runtime_config = data

    async def get_runtime_config(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._runtime_config)

    async def set_ctoai_snapshot(self, snapshot: dict[str, object]) -> None:
        async with self._lock:
            self._ctoai_snapshot = snapshot

    async def get_ctoai_snapshot(self) -> dict[str, object]:
        async with self._lock:
            return dict(self._ctoai_snapshot)

    async def upsert_directive(self, directive: TradeDirective) -> None:
        async with self._lock:
            self._directives[directive.directive_id] = directive

    async def get_directive(self, directive_id: str) -> TradeDirective | None:
        async with self._lock:
            return self._directives.get(directive_id)

    async def remove_directive(self, directive_id: str) -> None:
        async with self._lock:
            self._directives.pop(directive_id, None)

    async def list_directives(self) -> List[TradeDirective]:
        async with self._lock:
            return list(self._directives.values())

    async def set_positions(self, positions: List[dict[str, object]]) -> None:
        async with self._lock:
            self._positions = [dict(position) for position in positions]

    async def list_positions(self) -> List[dict[str, object]]:
        async with self._lock:
            return [dict(position) for position in self._positions]

    async def set_exposure_metrics(self, metrics: dict[str, Any]) -> None:
        async with self._lock:
            self._exposure_metrics = dict(metrics)

    async def get_exposure_metrics(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._exposure_metrics)

    async def set_service_health(self, name: str, status: dict[str, Any]) -> None:
        async with self._lock:
            self._service_health[name] = dict(status)

    async def get_service_health(self) -> dict[str, dict[str, Any]]:
        async with self._lock:
            return {name: dict(payload) for name, payload in self._service_health.items()}

    async def build_dashboard_state(self) -> dict[str, object]:
        async with self._lock:
            return {
                "market": {
                    "ignored": self._market.ignored,
                    "watch": self._market.watch,
                    "candidate": self._market.candidate,
                    "active": self._market.active,
                },
                "ctoai": dict(self._ctoai_snapshot),
                "directives": [directive.model_dump() for directive in self._directives.values()],
                "rejections": list(self._rejections),
                "positions": [dict(position) for position in self._positions],
                "exposure": dict(self._exposure_metrics),
                "risk_budget": dict(self._risk_budget),
                "config": dict(self._runtime_config),
                "services": {name: dict(payload) for name, payload in self._service_health.items()},
                "trade_stats": dict(self._trade_stats_overview),
            }

    async def set_trade_stats_overview(self, overview: dict[str, Any]) -> None:
        async with self._lock:
            data = dict(overview)
            if "updated_at" not in data:
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._trade_stats_overview = data

    async def get_trade_stats_overview(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._trade_stats_overview)

    async def set_risk_budget(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            data = dict(payload)
            if "updated_at" not in data:
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._risk_budget = data

    async def get_risk_budget(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._risk_budget)

    async def reset_for_clean_slate(self) -> None:
        async with self._lock:
            self._market = MarketOverview()
            self._ctoai_snapshot = {
                "mode": "manual",
                "state": "idle",
                "confidence": 0.0,
                "active_directives": [],
            }
            self._directives.clear()
            self._rejections.clear()
            self._positions = []
            self._exposure_metrics = {
                "total_abs_exposure": 0.0,
                "net_exposure": 0.0,
                "total_unrealized_pnl": 0.0,
                "positions_count": 0,
                "updated_at": None,
            }
            self._risk_budget = {
                "portfolio_limit": 0.0,
                "total_equity": 0.0,
                "available_equity": 0.0,
                "symbol_limits": {},
                "updated_at": None,
            }
            self._trade_stats_overview = {
                "summary": None,
                "recent": [],
                "last_trade": None,
                "updated_at": None,
            }
