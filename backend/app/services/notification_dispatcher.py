"""Notification dispatcher that pushes important alerts to an external webhook."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.services.rl_trainer import EXPERIENCE_KEY, FORCE_TRAIN_QUEUE, LAST_TRAIN_KEY, LATEST_METRICS_KEY

AUTO_RESEARCH_BACKLOG_KEY = "auto_research:backlog"
AUTO_RESEARCH_LAST_RUN_HASH = "auto_research:last_run"

LOGGER = get_logger(__name__)
HEARTBEAT_SECONDS = 60
STALE_MULTIPLIER = 2
RECOVERY_COOLDOWN_SECONDS = 900


class NotificationDispatcher:
    def __init__(self, config_manager: RuntimeConfigManager) -> None:
        self._config_manager = config_manager
        self._settings = get_settings()
        self._webhook_url = self._settings.notification_webhook_url
        self._channel = self._settings.notification_channel or "default"
        self._redis = redis.from_url(self._settings.redis_dsn, encoding="utf-8", decode_responses=True)
        self._http = httpx.AsyncClient(timeout=10.0)
        self._telegram_token = self._settings.telegram_bot_token
        self._telegram_chat_id = self._settings.telegram_chat_id
        self._last_buffer_ready: Optional[bool] = None
        self._last_queue_size: int = 0
        self._last_stale_alert: Optional[datetime] = None
        self._last_recovery: Optional[datetime] = None
        self._last_guard_state: Optional[str] = None
        self._last_volatility_state: Optional[str] = None
        self._last_guard_snapshot: Optional[datetime] = None
        self._daily_report_hour = self._settings.daily_report_hour_utc
        self._last_daily_report: Optional[str] = None
        self._auto_research_enabled_last: Optional[bool] = None
        self._auto_research_backlog_high: bool = False
        self._auto_research_stale: bool = False

    async def close(self) -> None:
        await self._redis.aclose()
        await self._http.aclose()

    async def run(self, stop_event: asyncio.Event) -> None:
        if not self._webhook_url and not (self._telegram_token and self._telegram_chat_id):
            LOGGER.info("notification_dispatcher_disabled_no_webhook")
            await stop_event.wait()
            return

        LOGGER.info("notification_dispatcher_started", channel=self._channel)
        try:
            while not stop_event.is_set():
                try:
                    await self._tick()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("notification_dispatcher_tick_failed", exc_info=exc)

                try:
                    await asyncio.wait_for(asyncio.shield(stop_event.wait()), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise
        finally:
            await self.close()
            LOGGER.info("notification_dispatcher_stopped")

    async def _tick(self) -> None:
        config = await self._config_manager.get_config()
        min_batch = max(32, config.rl_retrain_interval_hours * 16)
        train_interval = timedelta(hours=config.rl_retrain_interval_hours)
        self._daily_report_hour = config.daily_report_hour_utc

        now = datetime.now(timezone.utc)
        experience_count = await self._redis.llen(EXPERIENCE_KEY)
        queue_size = await self._redis.llen(FORCE_TRAIN_QUEUE)
        last_train_raw = await self._redis.get(LAST_TRAIN_KEY)
        last_train_at = self._parse_datetime(last_train_raw)

        buffer_ready = experience_count >= min_batch
        await self._handle_buffer_alert(buffer_ready, experience_count, min_batch)
        await self._handle_queue_alert(queue_size)
        await self._handle_stale_training_alert(last_train_at, train_interval)
        guard_snapshot = await self._handle_guard_alert()
        await self._handle_auto_research_alert(config)
        await self._maybe_send_daily_report(
            now,
            buffer_ready,
            experience_count,
            min_batch,
            queue_size,
            last_train_at,
            guard_snapshot,
        )

    async def _handle_buffer_alert(self, buffer_ready: bool, experience_count: int, min_batch: int) -> None:
        if self._last_buffer_ready is None:
            self._last_buffer_ready = buffer_ready
            return

        if buffer_ready and not self._last_buffer_ready:
            await self._send(
                "rl_buffer_ready",
                f"Буфер опыта пополнен: {experience_count}/{min_batch}. Обучение может стартовать.",
            )
            self._last_recovery = datetime.now(timezone.utc)
        elif not buffer_ready and self._last_buffer_ready:
            missing = max(0, min_batch - experience_count)
            await self._send(
                "rl_buffer_insufficient",
                f"Недостаточно опыта для обучения: {experience_count}/{min_batch}. Не хватает {missing} записей.",
            )
        self._last_buffer_ready = buffer_ready

    async def _handle_queue_alert(self, queue_size: int) -> None:
        if queue_size > 0 and self._last_queue_size == 0:
            await self._send(
                "rl_training_queue",
                f"В очереди принудительного обучения {queue_size} запрос(ов).",
            )
        elif queue_size == 0 and self._last_queue_size > 0:
            await self._send("rl_training_queue_cleared", "Очередь принудительного обучения очищена.")
        self._last_queue_size = queue_size

    async def _handle_stale_training_alert(self, last_train_at: Optional[datetime], interval: timedelta) -> None:
        if interval.total_seconds() <= 0:
            return

        now = datetime.now(timezone.utc)
        threshold = interval * STALE_MULTIPLIER
        if last_train_at is None:
            if not self._last_stale_alert:
                await self._send("rl_training_never_run", "RL тренер ещё ни разу не запускался.")
                self._last_stale_alert = now
            return

        age = now - last_train_at
        if age >= threshold:
            if not self._last_stale_alert or now - self._last_stale_alert >= threshold:
                await self._send(
                    "rl_training_stale",
                    f"RL тренер не запускался {self._format_timedelta(age)} (порог {self._format_timedelta(threshold)}).",
                )
                self._last_stale_alert = now
        else:
            if self._last_stale_alert and (not self._last_recovery or now - self._last_recovery >= timedelta(seconds=RECOVERY_COOLDOWN_SECONDS)):
                await self._send("rl_training_recovered", "RL тренер снова выполняет обучения в срок.")
                self._last_stale_alert = None
                self._last_recovery = now

    async def _send(self, event: str, message: str) -> None:
        payload: dict[str, Any] = {
            "event": event,
            "channel": self._channel,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._webhook_url:
            try:
                response = await self._http.post(self._webhook_url, json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                LOGGER.error("notification_dispatch_failed", event=event, error=str(exc))
            else:
                LOGGER.info("notification_dispatch_sent", event=event)
        if self._telegram_token and self._telegram_chat_id:
            await self._send_telegram(message)

    async def _send_telegram(self, text: str) -> None:
        assert self._telegram_token is not None
        assert self._telegram_chat_id is not None
        url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
        payload = {"chat_id": self._telegram_chat_id, "text": text}
        try:
            response = await self._http.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            LOGGER.error("telegram_dispatch_failed", error=str(exc))
        else:
            self._last_stale_alert = None
            self._last_recovery = datetime.now(timezone.utc)

    async def _handle_guard_alert(self) -> Optional[dict[str, Any]]:
        raw = await self._redis.get("auto_exposure:guard_state")
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.debug("guard_snapshot_invalid_json")
            return None

        guard_state = payload.get("equity_guard_state")
        volatility_state = payload.get("volatility_state")
        drawdown_pct = payload.get("equity_drawdown_pct") or 0.0
        portfolio_limit = payload.get("portfolio_limit")
        total_equity = payload.get("total_equity")
        timestamp_raw = payload.get("updated_at")
        snapshot_ts = self._parse_datetime(timestamp_raw)

        if guard_state and guard_state != self._last_guard_state:
            if guard_state == "halt":
                await self._send(
                    "equity_guard_halt",
                    "Equity guard перешёл в HALT: просадка {0:.2%}. Лимит портфеля сжат до {1} (equity {2}).".format(
                        drawdown_pct,
                        self._format_number(portfolio_limit),
                        self._format_number(total_equity),
                    ),
                )
            elif guard_state == "caution":
                await self._send(
                    "equity_guard_caution",
                    "Equity guard в состоянии CAUTION: просадка {0:.2%}. Лимит портфеля {1}.".format(
                        drawdown_pct,
                        self._format_number(portfolio_limit),
                    ),
                )
            elif guard_state == "normal" and self._last_guard_state in {"caution", "halt"}:
                await self._send("equity_guard_recovered", "Equity guard вернулся в NORMAL. Лимит портфеля {0}.".format(self._format_number(portfolio_limit)))
            self._last_guard_state = guard_state

        if volatility_state and volatility_state != self._last_volatility_state:
            if volatility_state in {"elevated", "turbulent"}:
                await self._send(
                    "volatility_guard_alert",
                    f"Волатильность {volatility_state.upper()}. Пересчитанные лимиты: {self._format_number(portfolio_limit)} портфель, equity {self._format_number(total_equity)}.",
                )
            elif volatility_state in {"calm", "choppy"} and self._last_volatility_state in {"elevated", "turbulent"}:
                await self._send("volatility_guard_normalized", "Волатильность вернулась к {volatility_state}. Лимиты восстановления: {0}.".format(self._format_number(portfolio_limit)))
            self._last_volatility_state = volatility_state

        if snapshot_ts:
            self._last_guard_snapshot = snapshot_ts
        return payload

    async def _handle_auto_research_alert(self, config: Any) -> None:
        enabled = getattr(config, "auto_research_enabled", False)
        if self._auto_research_enabled_last is None:
            self._auto_research_enabled_last = enabled
        elif enabled != self._auto_research_enabled_last:
            await self._send(
                "auto_research_enabled" if enabled else "auto_research_disabled",
                "Auto-research {state}.".format(state="включён" if enabled else "выключен"),
            )
            self._auto_research_enabled_last = enabled

        if not enabled:
            self._auto_research_backlog_high = False
            if self._auto_research_stale:
                self._auto_research_stale = False
            return

        batch_size = max(1, int(getattr(config, "auto_research_batch_size", 5)))
        backlog_size = await self._redis.zcard(AUTO_RESEARCH_BACKLOG_KEY)
        high_threshold = max(batch_size * 8, 50)
        recovery_threshold = max(batch_size * 4, 25)

        if backlog_size >= high_threshold and not self._auto_research_backlog_high:
            await self._send(
                "auto_research_backlog_high",
                "Бэклог авто-исследования вырос до {size} символов (порог {threshold}). Проверьте MarketWatcher и ResearchEngine.".format(
                    size=backlog_size,
                    threshold=high_threshold,
                ),
            )
            self._auto_research_backlog_high = True
        elif self._auto_research_backlog_high and backlog_size <= recovery_threshold:
            await self._send(
                "auto_research_backlog_normalized",
                "Бэклог авто-исследования снизился до {size}. Возвращаемся к нормальному режиму.".format(size=backlog_size),
            )
            self._auto_research_backlog_high = False

        interval_seconds = max(int(getattr(config, "auto_research_interval_minutes", 5.0) * 60), 60)
        stale_threshold = timedelta(seconds=interval_seconds * 4)
        last_run_values = await self._redis.hvals(AUTO_RESEARCH_LAST_RUN_HASH)
        latest_run = None
        for raw in last_run_values:
            stamp = self._parse_datetime(raw)
            if stamp and (latest_run is None or stamp > latest_run):
                latest_run = stamp

        now = datetime.now(timezone.utc)
        if latest_run is None:
            return

        if now - latest_run >= stale_threshold:
            if not self._auto_research_stale:
                await self._send(
                    "auto_research_stale",
                    "Auto-research не публикует снапшоты {age}. Проверьте сервис.".format(age=self._format_timedelta(now - latest_run)),
                )
                self._auto_research_stale = True
        elif self._auto_research_stale:
            await self._send("auto_research_recovered", "Auto-research снова активен. Последний запуск был {age} назад.".format(age=self._format_timedelta(now - latest_run)))
            self._auto_research_stale = False

    async def _maybe_send_daily_report(
        self,
        now: datetime,
        buffer_ready: bool,
        experience_count: int,
        min_batch: int,
        queue_size: int,
        last_train_at: Optional[datetime],
        guard_snapshot: Optional[dict[str, Any]],
    ) -> None:
        report_key = now.date().isoformat()
        if self._last_daily_report == report_key or now.hour < self._daily_report_hour:
            return

        metrics = await self._fetch_latest_metrics()
        guard_state = guard_snapshot.get("equity_guard_state") if guard_snapshot else None
        volatility_state = guard_snapshot.get("volatility_state") if guard_snapshot else None
        drawdown_pct = guard_snapshot.get("equity_drawdown_pct") if guard_snapshot else None
        portfolio_limit = guard_snapshot.get("portfolio_limit") if guard_snapshot else None
        total_equity = guard_snapshot.get("total_equity") if guard_snapshot else None
        volatility_factor = guard_snapshot.get("volatility_factor") if guard_snapshot else None

        lines = ["Ежедневный отчёт системы"]
        lines.append(
            "• Буфер опыта: {current}/{required} ({status})".format(
                current=experience_count,
                required=min_batch,
                status="готов" if buffer_ready else "недостаточно",
            )
        )
        lines.append(
            "• Очередь обучения: {queue}".format(queue=queue_size)
        )
        if last_train_at:
            lines.append(
                "• Последнее обучение: {ago} назад".format(ago=self._format_timedelta(now - last_train_at))
            )
        else:
            lines.append("• Последнее обучение: ещё не выполнялось")

        guard_desc = guard_state or "unknown"
        if drawdown_pct is not None:
            guard_desc += f" (drawdown {self._format_percent(drawdown_pct)})"
        lines.append(
            "• Equity guard: {state}, лимит {limit}, equity {equity}".format(
                state=guard_desc,
                limit=self._format_number(portfolio_limit),
                equity=self._format_number(total_equity),
            )
        )

        if volatility_state:
            lines.append(
                "• Волатильность: {state}{suffix}".format(
                    state=volatility_state,
                    suffix=f" (factor {volatility_factor:.2f})" if isinstance(volatility_factor, (int, float)) else "",
                )
            )

        if metrics:
            lines.append(
                "• RL win rate: {win}, Sharpe: {sharpe}, Max DD: {dd}".format(
                    win=self._format_percent(metrics.get("win_rate")),
                    sharpe=self._format_number(metrics.get("sharpe_ratio")),
                    dd=self._format_percent(metrics.get("max_drawdown")),
                )
            )
            last_pnl = metrics.get("last_trade_pnl_pct")
            if last_pnl is not None:
                lines.append(f"• Последняя сделка: {self._format_percent(last_pnl)} PnL")

        await self._send("daily_status_report", "\n".join(lines))
        self._last_daily_report = report_key

    async def _fetch_latest_metrics(self) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(LATEST_METRICS_KEY)
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            LOGGER.debug("latest_metrics_invalid_json")
            return None
        return payload

    @staticmethod
    def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    @staticmethod
    def _format_timedelta(delta: timedelta) -> str:
        seconds = int(delta.total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if hours and minutes:
            return f"{hours}ч {minutes}м"
        if hours:
            return f"{hours}ч"
        if minutes:
            return f"{minutes}м"
        return f"{seconds}с"

    @staticmethod
    def _format_number(value: Any) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):,.2f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _format_percent(value: Any) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value)*100:.2f}%"
        except (TypeError, ValueError):
            return str(value)


async def run_notification_dispatcher(stop_event: asyncio.Event, config_manager: RuntimeConfigManager) -> None:
    dispatcher = NotificationDispatcher(config_manager)
    try:
        await dispatcher.run(stop_event)
    finally:
        await dispatcher.close()
