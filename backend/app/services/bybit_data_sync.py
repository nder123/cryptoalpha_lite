from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.runtime_config import RuntimeConfigManager
from app.exchange.bybit import BybitClient
from app.repositories.bybit_sync import ExchangeDataRepository


class BybitDataSynchronizer:
    """Synchronize Bybit executions, transactions, and equity snapshots."""

    def __init__(
        self,
        config_manager: RuntimeConfigManager,
        lookback_days: int = 30,
        poll_interval_seconds: float = 60.0,
    ) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        self._config_manager = config_manager
        self._lookback_days = lookback_days
        self._poll_interval = poll_interval_seconds
        # Bybit restricts execution/transaction queries to 7-day windows.
        self._max_window = timedelta(days=7) - timedelta(seconds=1)
        self._client = BybitClient()
        self._repo = ExchangeDataRepository()
        self._credentials_missing_logged = False

    async def run(self, stop_event: asyncio.Event) -> None:
        try:
            await self._initial_backfill(stop_event)
            while not stop_event.is_set():
                await self._sync_recent()
                await self._capture_equity_snapshot()
                await asyncio.sleep(self._poll_interval)
        finally:
            await self._client.close()

    async def _initial_backfill(self, stop_event: asyncio.Event) -> None:
        if stop_event.is_set():
            return
        if not await self._should_sync():
            return

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self._lookback_days)
        self._logger.info(
            "bybit_sync_backfill_started",
            start=start_time.isoformat(),
            end=end_time.isoformat(),
        )
        for window_start, window_end in self._iter_windows(start_time, end_time):
            await self._sync_executions(start_time=window_start, end_time=window_end)
            await self._sync_closed_pnl(start_time=window_start, end_time=window_end)
            await self._sync_transactions(start_time=window_start, end_time=window_end)
        await self._capture_equity_snapshot()
        self._logger.info("bybit_sync_backfill_finished")

    async def _sync_recent(self) -> None:
        if not await self._should_sync():
            return

        last_trade_time = await self._repo.last_trade_time()
        start_time = None
        if last_trade_time is not None:
            start_time = last_trade_time - timedelta(minutes=5)
        await self._sync_executions(start_time=start_time)

        await self._sync_closed_pnl(start_time=start_time)

        last_tx_time = await self._repo.last_transaction_time()
        tx_start = last_tx_time - timedelta(minutes=5) if last_tx_time else start_time
        await self._sync_transactions(start_time=tx_start)

    async def _sync_executions(
        self,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        cursor: str | None = None
        total = 0
        while True:
            rows, cursor = await self._client.fetch_executions(
                start_time=start_time,
                end_time=end_time,
                cursor=cursor,
            )
            if not rows:
                break
            total += await self._repo.upsert_trades(rows)
            if not cursor:
                break
        if total:
            self._logger.info("bybit_sync_executions", count=total)

    async def _sync_closed_pnl(
        self,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        cursor: str | None = None
        total = 0
        aggregated: list[dict] = []
        while True:
            rows, cursor = await self._client.fetch_closed_pnl(
                start_time=start_time,
                end_time=end_time,
                cursor=cursor,
            )
            if not rows:
                break
            total += len(rows)
            aggregated.extend(
                {
                    "transaction_id": f"closed-pnl-{row.get('order_id')}-{row.get('trade_time')}",
                    "reference_id": row.get("order_id"),
                    "type": "CLOSED_PNL",
                    "sub_type": row.get("side"),
                    "amount": row.get("realized_pnl"),
                    "currency": "USDT",
                    "fee": row.get("cum_fee"),
                    "trade_time": row.get("trade_time"),
                }
                for row in rows
            )
            if not cursor:
                break
        if aggregated:
            await self._repo.upsert_transactions(aggregated)
        if total:
            self._logger.info("bybit_sync_closed_pnl", count=total)

    async def _sync_transactions(
        self,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        cursor: str | None = None
        total = 0
        while True:
            rows, cursor = await self._client.fetch_account_transactions(
                start_time=start_time,
                end_time=end_time,
                cursor=cursor,
            )
            if not rows:
                break
            total += await self._repo.upsert_transactions(rows)
            if not cursor:
                break
        if total:
            self._logger.info("bybit_sync_transactions", count=total)

    async def _capture_equity_snapshot(self) -> None:
        if not await self._should_sync():
            return
        try:
            wallet = await self._client.fetch_wallet_balance()
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("bybit_sync_equity_failed", error=str(exc))
            return
        snapshot = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "total_equity": wallet.get("total_equity"),
            "wallet_balance": wallet.get("wallet_balance"),
            "available_balance": wallet.get("available_to_withdraw"),
            "currency": "USDT",
        }
        await self._repo.upsert_equity_snapshots([snapshot])
        self._logger.info("bybit_sync_equity_snapshot")

    async def _should_sync(self) -> bool:
        try:
            config = await self._config_manager.get_config()
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("bybit_sync_config_error", error=str(exc))
            return False
        if not self._has_credentials():
            await self._handle_missing_credentials()
            return False
        if config.dry_run:
            self._logger.debug("bybit_sync_skipped_dry_run")
            return False
        return True

    def _iter_windows(self, start: datetime, end: datetime) -> Iterable[tuple[datetime, datetime]]:
        current_start = start
        window_delta = self._max_window
        while current_start < end:
            current_end = min(current_start + window_delta, end)
            yield current_start, current_end
            # Advance by 1 millisecond to avoid re-querying the same boundary.
            current_start = current_end + timedelta(milliseconds=1)

    def _has_credentials(self) -> bool:
        return bool(self._settings.bybit_api_key and self._settings.bybit_api_secret)

    async def _handle_missing_credentials(self) -> None:
        if self._credentials_missing_logged:
            return
        self._logger.warning("bybit_sync_disabled_no_credentials")
        self._credentials_missing_logged = True


async def run_bybit_data_sync(
    stop_event: asyncio.Event,
    config_manager: RuntimeConfigManager,
) -> None:
    synchronizer = BybitDataSynchronizer(config_manager)
    await synchronizer.run(stop_event)
