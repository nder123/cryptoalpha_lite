from __future__ import annotations

from typing import Any, Optional

from app.exchange.adapter import ExchangeAdapter, ExchangeOrderStatus, ExchangeSubmitResult
from app.exchange.bybit import BybitClient
from app.services.trading_gate import assert_trading_allowed


class BybitExchangeAdapter:
    def __init__(self, client: BybitClient | None = None) -> None:
        self._client = client or BybitClient()

    async def submit(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        price: Optional[str] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        position_idx: int | None = None,
        order_link_id: str | None = None,
        take_profit: Optional[str] = None,
        stop_loss: Optional[str] = None,
    ) -> ExchangeSubmitResult:
        # SAFE_MODE / CRITICAL gate. Last line of defense before real exchange
        # contact. See docs/safe_mode_enforcement_v1.md §3.
        assert_trading_allowed(
            component="bybit_adapter",
            attempted_action=f"submit_{order_type}_{side}_{symbol}",
        )
        result = await self._client.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            position_idx=position_idx,
            order_link_id=order_link_id,
            take_profit=take_profit,
            stop_loss=stop_loss,
        )
        return ExchangeSubmitResult(
            exchange_order_id=result.order_id or "",
            status=result.status or "",
            qty=float(result.qty),
        )

    async def cancel(self, *, symbol: str, order_id: str) -> None:
        await self._client.cancel_order(symbol=symbol, order_id=order_id)

    async def fetch_status(self, *, symbol: str, order_id: str) -> ExchangeOrderStatus | None:
        info = await self._client.get_order_status(symbol=symbol, order_id=order_id)
        if info is None:
            return None
        return ExchangeOrderStatus(
            status=str(info.status),
            avg_price=info.avg_price,
            cum_exec_qty=info.cum_exec_qty,
            cum_exec_fee=info.cum_exec_fee,
        )

    async def fetch_status_by_link_id(
        self, *, symbol: str, order_link_id: str
    ) -> ExchangeOrderStatus | None:
        entry = await self._client.get_order_status_by_link_id_raw(
            symbol=symbol,
            order_link_id=order_link_id,
        )
        if entry is None:
            return None
        return ExchangeOrderStatus(
            status=str(entry.get("orderStatus") or ""),
            avg_price=None,
            cum_exec_qty=None,
            cum_exec_fee=None,
        )

    async def fetch_open_orders(
        self, *, symbol: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        return await self._client.fetch_open_orders(symbol=symbol, limit=limit)

    async def fetch_recent_orders(
        self,
        *,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self._client.fetch_recent_orders(symbol=symbol, limit=limit)

    async def fetch_positions(
        self, *, settle_coin: str | None = "USDT", symbol: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._client.fetch_positions(settle_coin=settle_coin, symbol=symbol)
