"""Editable runtime configuration for the CTO-AI platform."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, Field

from app.core.config import Settings


class RuntimeConfig(BaseModel):
    """Subset of configuration values that can be adjusted at runtime."""

    market_scan_interval_seconds: float = Field(default=10.0, ge=1.0, le=300.0)
    research_refresh_interval_seconds: float = Field(default=20.0, ge=5.0, le=600.0)
    research_max_hypotheses_per_minute: int = Field(default=60, ge=1, le=600)
    funding_threshold: float = Field(default=0.005, ge=0.0, le=0.1)
    volatility_threshold: float = Field(default=0.015, ge=0.0, le=0.1)
    max_candidate_symbols: int = Field(default=40, ge=1, le=50)
    max_portfolio_exposure_usdt: float = Field(default=15_000.0, ge=1.0, le=1_000_000.0)
    max_symbol_allocation_pct: float = Field(default=0.1, ge=0.01, le=1.0)
    max_leverage: float = Field(default=3.0, ge=1.0, le=50.0)
    min_confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    default_stop_loss_pct: float = Field(default=0.005, ge=0.0, le=1.0)
    default_take_profit_pct: float = Field(default=0.01, ge=0.0, le=2.0)
    risk_target_pct: float = Field(default=0.2, ge=0.0, le=1.0)
    volatility_sensitivity: float = Field(default=0.5, ge=0.0, le=2.0)
    min_trade_notional_usdt: float = Field(default=50.0, ge=0.0, le=100_000.0)
    execution_retry_attempts: int = Field(default=3, ge=0, le=10)
    execution_retry_backoff_seconds: float = Field(default=1.0, ge=0.0, le=30.0)
    execution_degraded_threshold: int = Field(default=3, ge=1, le=20)
    execution_degraded_cooldown_seconds: float = Field(default=120.0, ge=10.0, le=3600.0)
    position_manager_poll_interval_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    position_manager_force_close_minutes: float = Field(default=180.0, ge=1.0, le=1440.0)
    position_manager_use_market_exit: bool = Field(default=True)
    position_manager_limit_exit_timeout_seconds: float = Field(default=20.0, ge=0.0, le=600.0)
    symbol_denylist: list[str] = Field(default_factory=list)
    auto_exposure_enabled: bool = Field(default=False)
    auto_exposure_portfolio_pct: float = Field(default=0.1, ge=0.0, le=1.0)
    auto_symbol_allocation_pct: float = Field(default=0.1, ge=0.0, le=1.0)
    dry_run: bool = Field(default=True)
    auto_research_enabled: bool = Field(default=True)
    auto_research_interval_minutes: float = Field(default=5.0, ge=0.1, le=240.0)
    auto_research_batch_size: int = Field(default=5, ge=1, le=50)
    rl_enabled: bool = Field(default=False)
    rl_policy_min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    rl_retrain_interval_hours: int = Field(default=6, ge=1, le=8760)
    rl_experience_window_days: int = Field(default=30, ge=1, le=180)
    daily_report_hour_utc: int = Field(default=21, ge=0, le=23)

    rl_autopilot_enabled: bool = Field(default=False)
    rl_autopilot_symbol: str = Field(default="BTCUSDT", min_length=2, max_length=30)
    rl_autopilot_interval_seconds: float = Field(default=300.0, ge=30.0, le=86_400.0)
    rl_autopilot_hold_seconds: float = Field(default=90.0, ge=5.0, le=86_400.0)
    rl_autopilot_quantity: float = Field(default=0.001, gt=0.0, le=10_000.0)
    rl_autopilot_leverage: float = Field(default=1.0, ge=1.0, le=50.0)
    rl_autopilot_direction: str = Field(default="alternate")

    dry_run_fill_simulator_enabled: bool = Field(default=False)
    dry_run_fill_simulator_delay_seconds: float = Field(default=2.0, ge=0.0, le=60.0)
    dry_run_fill_simulator_slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    dry_run_fill_simulator_spread_bps: float = Field(default=2.0, ge=0.0, le=500.0)
    dry_run_fill_simulator_drift_bps_per_minute: float = Field(default=0.0, ge=-500.0, le=500.0)
    dry_run_fill_simulator_volatility_bps: float = Field(default=10.0, ge=0.0, le=2000.0)
    dry_run_fill_simulator_fee_bps: float = Field(default=10.0, ge=0.0, le=500.0)

    max_trades_per_day: int = Field(default=50, ge=0, le=10_000)
    max_daily_loss_usdt: float = Field(default=50.0, ge=0.0, le=1_000_000.0)
    max_consecutive_losses: int = Field(default=10, ge=0, le=10_000)

    updated_at: datetime | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "RuntimeConfig":
        return cls(
            market_scan_interval_seconds=settings.market_scan_interval_seconds,
            research_refresh_interval_seconds=settings.research_refresh_interval_seconds,
            research_max_hypotheses_per_minute=settings.research_max_hypotheses_per_minute,
            funding_threshold=settings.funding_threshold,
            volatility_threshold=settings.volatility_threshold,
            max_candidate_symbols=settings.max_candidate_symbols,
            max_portfolio_exposure_usdt=settings.max_portfolio_exposure_usdt,
            max_symbol_allocation_pct=settings.max_symbol_allocation_pct,
            max_leverage=settings.max_leverage,
            min_confidence_threshold=settings.min_confidence_threshold,
            default_stop_loss_pct=settings.default_stop_loss_pct,
            default_take_profit_pct=settings.default_take_profit_pct,
            risk_target_pct=settings.risk_target_pct,
            volatility_sensitivity=settings.volatility_sensitivity,
            min_trade_notional_usdt=settings.min_trade_notional_usdt,
            execution_retry_attempts=settings.execution_retry_attempts,
            execution_retry_backoff_seconds=settings.execution_retry_backoff_seconds,
            execution_degraded_threshold=settings.execution_degraded_threshold,
            execution_degraded_cooldown_seconds=settings.execution_degraded_cooldown_seconds,
            position_manager_poll_interval_seconds=settings.position_manager_poll_interval_seconds,
            position_manager_force_close_minutes=settings.position_manager_force_close_minutes,
            position_manager_use_market_exit=settings.position_manager_use_market_exit,
            position_manager_limit_exit_timeout_seconds=getattr(settings, "position_manager_limit_exit_timeout_seconds", 20.0),
            symbol_denylist=getattr(settings, "symbol_denylist", []) or [],
            auto_exposure_enabled=settings.auto_exposure_enabled,
            auto_exposure_portfolio_pct=settings.auto_exposure_portfolio_pct,
            auto_symbol_allocation_pct=settings.auto_symbol_allocation_pct,
            dry_run=settings.dry_run,
            auto_research_enabled=settings.auto_research_enabled,
            auto_research_interval_minutes=settings.auto_research_interval_minutes,
            auto_research_batch_size=settings.auto_research_batch_size,
            rl_enabled=settings.rl_enabled,
            rl_policy_min_confidence=settings.rl_policy_min_confidence,
            rl_retrain_interval_hours=settings.rl_retrain_interval_hours,
            rl_experience_window_days=settings.rl_experience_window_days,
            daily_report_hour_utc=settings.daily_report_hour_utc,
            max_trades_per_day=getattr(settings, "max_trades_per_day", 50),
            max_daily_loss_usdt=getattr(settings, "max_daily_loss_usdt", 50.0),
            max_consecutive_losses=getattr(settings, "max_consecutive_losses", 10),
            updated_at=None,
        )

    def merged(self, overrides: dict[str, Any] | None) -> "RuntimeConfig":
        if not overrides:
            return self
        return self.model_copy(update=overrides)


class RuntimeConfigUpdate(BaseModel):
    """Partial update payload for runtime configuration."""

    market_scan_interval_seconds: float | None = Field(default=None, ge=1.0, le=300.0)
    research_refresh_interval_seconds: float | None = Field(default=None, ge=5.0, le=600.0)
    funding_threshold: float | None = Field(default=None, ge=0.0, le=0.1)
    volatility_threshold: float | None = Field(default=None, ge=0.0, le=0.1)
    max_candidate_symbols: int | None = Field(default=None, ge=1, le=50)
    max_portfolio_exposure_usdt: float | None = Field(default=None, ge=1.0, le=1_000_000.0)
    max_symbol_allocation_pct: float | None = Field(default=None, ge=0.01, le=1.0)
    max_leverage: float | None = Field(default=None, ge=1.0, le=50.0)
    min_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    default_stop_loss_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    default_take_profit_pct: float | None = Field(default=None, ge=0.0, le=2.0)
    risk_target_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    volatility_sensitivity: float | None = Field(default=None, ge=0.0, le=2.0)
    min_trade_notional_usdt: float | None = Field(default=None, ge=0.0, le=100_000.0)
    research_max_hypotheses_per_minute: int | None = Field(default=None, ge=1, le=600)
    execution_retry_attempts: int | None = Field(default=None, ge=0, le=10)
    execution_retry_backoff_seconds: float | None = Field(default=None, ge=0.0, le=30.0)
    execution_degraded_threshold: int | None = Field(default=None, ge=1, le=20)
    execution_degraded_cooldown_seconds: float | None = Field(default=None, ge=10.0, le=3600.0)
    position_manager_poll_interval_seconds: float | None = Field(default=None, ge=1.0, le=60.0)
    position_manager_force_close_minutes: float | None = Field(default=None, ge=1.0, le=1440.0)
    position_manager_use_market_exit: bool | None = None
    position_manager_limit_exit_timeout_seconds: float | None = Field(default=None, ge=0.0, le=600.0)
    symbol_denylist: list[str] | None = None
    auto_exposure_enabled: bool | None = None
    auto_exposure_portfolio_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    auto_symbol_allocation_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    dry_run: bool | None = None
    auto_research_enabled: bool | None = None
    auto_research_interval_minutes: float | None = Field(default=None, ge=0.1, le=240.0)
    auto_research_batch_size: int | None = Field(default=None, ge=1, le=50)
    rl_enabled: bool | None = None
    rl_policy_min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rl_retrain_interval_hours: int | None = Field(default=None, ge=1, le=8760)
    rl_experience_window_days: int | None = Field(default=None, ge=1, le=180)

    rl_autopilot_enabled: bool | None = None
    rl_autopilot_symbol: str | None = Field(default=None, min_length=2, max_length=30)
    rl_autopilot_interval_seconds: float | None = Field(default=None, ge=30.0, le=86_400.0)
    rl_autopilot_hold_seconds: float | None = Field(default=None, ge=5.0, le=86_400.0)
    rl_autopilot_quantity: float | None = Field(default=None, gt=0.0, le=10_000.0)
    rl_autopilot_leverage: float | None = Field(default=None, ge=1.0, le=50.0)
    rl_autopilot_direction: str | None = None

    dry_run_fill_simulator_enabled: bool | None = None
    dry_run_fill_simulator_delay_seconds: float | None = Field(default=None, ge=0.0, le=60.0)
    dry_run_fill_simulator_slippage_bps: float | None = Field(default=None, ge=0.0, le=500.0)
    dry_run_fill_simulator_spread_bps: float | None = Field(default=None, ge=0.0, le=500.0)
    dry_run_fill_simulator_drift_bps_per_minute: float | None = Field(default=None, ge=-500.0, le=500.0)
    dry_run_fill_simulator_volatility_bps: float | None = Field(default=None, ge=0.0, le=2000.0)
    dry_run_fill_simulator_fee_bps: float | None = Field(default=None, ge=0.0, le=500.0)

    max_trades_per_day: int | None = Field(default=None, ge=0, le=10_000)
    max_daily_loss_usdt: float | None = Field(default=None, ge=0.0, le=1_000_000.0)
    max_consecutive_losses: int | None = Field(default=None, ge=0, le=10_000)

    def to_updates(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class RuntimeConfigManager:
    """Holds runtime overrides on top of static settings."""

    def __init__(self, settings: Settings, overrides: dict[str, Any] | None = None) -> None:
        self._base = RuntimeConfig.from_settings(settings)
        self._overrides: dict[str, Any] = overrides or {}
        self._lock = asyncio.Lock()

    async def get_config(self) -> RuntimeConfig:
        async with self._lock:
            config = self._current_locked()
            return config

    async def update(self, updates: dict[str, Any]) -> RuntimeConfig:
        async with self._lock:
            self._overrides.update(updates)
            return self._current_locked()

    async def set_overrides(self, overrides: dict[str, Any]) -> RuntimeConfig:
        async with self._lock:
            self._overrides = overrides
            return self._current_locked()

    async def export_overrides(self) -> Dict[str, Any]:
        async with self._lock:
            return dict(self._overrides)

    def _current_locked(self) -> RuntimeConfig:
        config = self._base.merged(self._overrides)
        config.updated_at = datetime.now(timezone.utc)
        return config
