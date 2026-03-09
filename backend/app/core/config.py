"""Application configuration using Pydantic settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the CTO-AI backend."""

    model_config = SettingsConfigDict(
        env_file=(
            str(_BACKEND_ROOT / ".env"),
            str(_BACKEND_ROOT / ".env.local"),
        ),
        env_nested_delimiter="__",
    )

    app_name: str = Field(default="CTO-AI Backend")
    environment: Literal["local", "test", "production"] = Field(default="local")

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    redis_dsn: str = Field(default="redis://redis:6379/0")
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://ctoai:ctoai@postgres:5432/ctoai"
    )

    bybit_api_key: Optional[str] = None
    bybit_api_secret: Optional[str] = None
    bybit_base_url: str = Field(default="https://api-testnet.bybit.com")
    dry_run: bool = Field(default=True)

    market_scan_interval_seconds: float = Field(default=10.0)
    research_refresh_interval_seconds: float = Field(default=20.0)
    research_max_hypotheses_per_minute: int = Field(default=60, ge=1, le=600)
    risk_evaluation_timeout_seconds: float = Field(default=15.0)
    execution_poll_interval_seconds: float = Field(default=5.0)
    execution_retry_attempts: int = Field(default=3, ge=0, le=10)
    execution_retry_backoff_seconds: float = Field(default=1.0, ge=0.0, le=30.0)
    execution_degraded_threshold: int = Field(default=3, ge=1, le=20)
    execution_degraded_cooldown_seconds: float = Field(
        default=120.0, ge=10.0, le=3600.0
    )
    market_concurrency: int = Field(default=4)
    research_window_minutes: int = Field(default=60)
    funding_threshold: float = Field(default=0.005)
    volatility_threshold: float = Field(default=0.015)
    max_candidate_symbols: int = Field(default=40, gt=0)

    max_leverage: float = Field(default=3.0)
    max_portfolio_exposure_usdt: float = Field(default=15000.0)
    max_open_positions: int = Field(default=3)
    max_symbol_allocation_pct: float = Field(default=0.1)
    max_daily_loss_pct: float = Field(default=0.03)
    min_confidence_threshold: float = Field(default=0.25)
    default_stop_loss_pct: float = Field(default=0.005)
    default_take_profit_pct: float = Field(default=0.01)
    risk_target_pct: float = Field(default=0.2)
    volatility_sensitivity: float = Field(default=0.5)
    min_trade_notional_usdt: float = Field(default=50.0)

    auto_exposure_enabled: bool = Field(default=False)
    auto_exposure_portfolio_pct: float = Field(default=0.1)
    auto_symbol_allocation_pct: float = Field(default=0.1)

    auto_research_enabled: bool = Field(default=True)
    auto_research_interval_minutes: float = Field(default=5.0)
    auto_research_batch_size: int = Field(default=5, ge=1, le=50)

    position_manager_poll_interval_seconds: float = Field(default=5.0)
    position_manager_force_close_minutes: float = Field(default=180.0)
    position_manager_use_market_exit: bool = Field(default=True)

    rl_enabled: bool = Field(default=False)
    rl_policy_min_confidence: float = Field(default=0.7)
    rl_retrain_interval_hours: int = Field(default=6)
    rl_experience_window_days: int = Field(default=30)

    notification_webhook_url: Optional[str] = None
    notification_channel: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    daily_report_hour_utc: int = Field(default=21, ge=0, le=23)

    websocket_broadcast_channel: str = Field(default="ctoai.broadcast")
    redis_stream_maxlen: int | None = Field(default=5000, ge=100)

    runtime_overrides_path: str | None = Field(default=None)

    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
