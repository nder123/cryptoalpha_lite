"""Bybit USDT-M futures exchange adapter."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

IGNORED_TRANSACTION_TYPES = {"SETTLEMENT"}


@dataclass(slots=True)
class SymbolTicker:
    symbol: str
    last_price: float
    price_24h_pct: float
    volume_24h: float
    funding_rate: float
    open_interest: float
    turnover_24h: float


@dataclass(slots=True)
class SymbolFilters:
    min_order_qty: Decimal
    qty_step: Decimal
    tick_size: Decimal
    min_notional: Optional[Decimal] = None


@dataclass(slots=True)
class OrderPlacementResult:
    order_id: str
    status: str
    qty: float


@dataclass(slots=True)
class OrderStatusInfo:
    status: str
    avg_price: Optional[float]
    cum_exec_qty: Optional[float]
    cum_exec_fee: Optional[float]
    updated_at: Optional[datetime]


class BybitClient:
    """Lightweight async client for Bybit endpoints."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._logger = get_logger(__name__)
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        timeout = httpx.Timeout(20.0, connect=10.0)
        self._client = httpx.AsyncClient(
            base_url=self._settings.bybit_base_url, limits=limits, timeout=timeout
        )
        self._account_client = httpx.AsyncClient(
            base_url=self._settings.bybit_base_url,
            limits=limits,
            timeout=timeout,
        )
        self._lock = asyncio.Lock()
        self._instrument_cache: Dict[str, SymbolFilters] = {}

    async def close(self) -> None:
        await self._client.aclose()
        await self._account_client.aclose()

    async def _get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        *,
        max_attempts: int = 5,
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                response = await self._client.get(path, params=params)
                response.raise_for_status()
                data = response.json()
                if data.get("retCode") not in (0, "0"):
                    raise RuntimeError(f"Bybit API error: {data}")
                return data["result"]
            except httpx.TimeoutException:
                attempt += 1
                if attempt >= max_attempts:
                    raise
                self._logger.warning(
                    "bybit_public_timeout_retry",
                    path=path,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                await asyncio.sleep(min(2.0 * attempt, 5.0))
            except httpx.RequestError as exc:
                attempt += 1
                if attempt >= max_attempts:
                    raise
                self._logger.warning(
                    "bybit_public_connect_retry",
                    path=path,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(exc),
                )
                await asyncio.sleep(min(2.0 * attempt, 10.0))

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_optional_float(value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _decode_cursor(value: str | None) -> str | None:
        if not value:
            return None
        decoded = value
        for _ in range(3):
            new_value = urllib.parse.unquote(decoded)
            if new_value == decoded:
                break
            decoded = new_value
        return decoded or None

    @staticmethod
    def _to_milliseconds(value: Optional[datetime | int | float]) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return int(value.timestamp() * 1000)
        return None

    @staticmethod
    def _timestamp_to_iso(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        try:
            raw = int(str(value))
        except (TypeError, ValueError):
            return None
        try:
            return datetime.fromtimestamp(raw / 1000, tz=timezone.utc).isoformat()
        except (OverflowError, ValueError):
            return None

    async def list_perpetual_symbols(self) -> List[str]:
        result = await self._get(
            "/v5/market/instruments-info",
            params={"category": "linear", "limit": 200},
        )
        instruments = result.get("list", [])
        symbols = [
            entry["symbol"]
            for entry in instruments
            if entry.get("contractType") == "LinearPerpetual"
        ]
        return symbols

    async def get_symbol_filters(self, symbol: str) -> SymbolFilters:
        cached = self._instrument_cache.get(symbol)
        if cached:
            return cached

        result = await self._get(
            "/v5/market/instruments-info",
            params={"category": "linear", "symbol": symbol},
        )
        instruments = result.get("list", [])
        if not instruments:
            raise RuntimeError(f"Symbol {symbol} is not available on Bybit")

        instrument = instruments[0]
        lot_filter = instrument.get("lotSizeFilter") or {}
        price_filter = instrument.get("priceFilter") or {}

        filters = SymbolFilters(
            min_order_qty=self._to_decimal(lot_filter.get("minOrderQty", "0")),
            qty_step=self._to_decimal(lot_filter.get("qtyStep", "1")),
            tick_size=self._to_decimal(price_filter.get("tickSize", "0.5")),
            min_notional=(
                self._to_decimal(lot_filter.get("minOrderAmt"))
                if lot_filter.get("minOrderAmt")
                else None
            ),
        )
        self._instrument_cache[symbol] = filters
        return filters

    async def fetch_tickers(self) -> Dict[str, SymbolTicker]:
        result = await self._get(
            "/v5/market/tickers",
            params={"category": "linear"},
        )
        tickers: Dict[str, SymbolTicker] = {}
        for entry in result.get("list", []):
            symbol = entry["symbol"]
            funding = self._to_float(entry.get("fundingRate"))
            tickers[symbol] = SymbolTicker(
                symbol=symbol,
                last_price=self._to_float(entry.get("lastPrice")),
                price_24h_pct=self._to_float(entry.get("price24hPcnt")),
                volume_24h=self._to_float(entry.get("volume24h")),
                funding_rate=funding,
                open_interest=self._to_float(entry.get("openInterestValue")),
                turnover_24h=self._to_float(entry.get("turnover24h")),
            )
        return tickers

    async def get_symbol_ticker(self, symbol: str) -> SymbolTicker:
        result = await self._get(
            "/v5/market/tickers",
            params={"category": "linear", "symbol": symbol},
        )
        entries = result.get("list", [])
        if not entries:
            raise RuntimeError(f"Ticker for {symbol} is not available")
        entry = entries[0]
        return SymbolTicker(
            symbol=entry["symbol"],
            last_price=self._to_float(entry.get("lastPrice")),
            price_24h_pct=self._to_float(entry.get("price24hPcnt")),
            volume_24h=self._to_float(entry.get("volume24h")),
            funding_rate=self._to_float(entry.get("fundingRate")),
            open_interest=self._to_float(entry.get("openInterestValue")),
            turnover_24h=self._to_float(entry.get("turnover24h")),
        )

    async def fetch_kline(
        self, symbol: str, interval: str = "60", limit: int = 24
    ) -> List[dict[str, Any]]:
        result = await self._get(
            "/derivatives/v3/public/kline",
            params={
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
        )
        return result.get("list", [])

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        qty: str,
        price: Optional[str] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        position_idx: int | None = None,
        *,
        take_profit: Optional[str] = None,
        stop_loss: Optional[str] = None,
        tp_trigger_by: Optional[str] = "LastPrice",
        sl_trigger_by: Optional[str] = "LastPrice",
    ) -> OrderPlacementResult:
        filters = await self.get_symbol_filters(symbol)
        qty_decimal = self._to_decimal(qty)
        if qty_decimal <= 0:
            raise RuntimeError("Order quantity must be positive")
        normalized_qty = qty_decimal.quantize(filters.qty_step, rounding=ROUND_DOWN)
        if normalized_qty <= 0:
            normalized_qty = filters.min_order_qty
        if normalized_qty < filters.min_order_qty:
            raise RuntimeError(
                f"Order quantity {qty_decimal} below Bybit minimum {filters.min_order_qty}"
            )

        normalized_price: Optional[Decimal] = None
        if price is not None:
            price_decimal = self._to_decimal(price)
            if price_decimal <= 0:
                raise RuntimeError("Order price must be positive")
            normalized_price = price_decimal.quantize(
                filters.tick_size, rounding=ROUND_HALF_UP
            )
            if normalized_price <= 0:
                raise RuntimeError("Order price must be positive after rounding")

        if normalized_price is not None and filters.min_notional is not None:
            notional = normalized_price * normalized_qty
            if notional < filters.min_notional:
                raise RuntimeError(
                    f"Order notional {notional} below Bybit minimum {filters.min_notional}"
                )

        normalized_tp: Optional[Decimal] = None
        if take_profit is not None:
            tp_decimal = self._to_decimal(take_profit)
            if tp_decimal <= 0:
                raise RuntimeError("Take-profit price must be positive")
            normalized_tp = tp_decimal.quantize(
                filters.tick_size, rounding=ROUND_HALF_UP
            )
            if normalized_tp <= 0:
                raise RuntimeError("Take-profit price must be positive after rounding")

        normalized_sl: Optional[Decimal] = None
        if stop_loss is not None:
            sl_decimal = self._to_decimal(stop_loss)
            if sl_decimal <= 0:
                raise RuntimeError("Stop-loss price must be positive")
            normalized_sl = sl_decimal.quantize(
                filters.tick_size, rounding=ROUND_HALF_UP
            )
            if normalized_sl <= 0:
                raise RuntimeError("Stop-loss price must be positive after rounding")

        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": self._decimal_to_str(normalized_qty),
            "timeInForce": time_in_force,
            "reduceOnly": reduce_only,
        }
        if position_idx is not None:
            payload["positionIdx"] = int(position_idx)
        if normalized_price is not None:
            payload["price"] = self._decimal_to_str(normalized_price)
        if normalized_tp is not None:
            payload["takeProfit"] = self._decimal_to_str(normalized_tp)
            payload["tpTriggerBy"] = tp_trigger_by or "LastPrice"
        if normalized_sl is not None:
            payload["stopLoss"] = self._decimal_to_str(normalized_sl)
            payload["slTriggerBy"] = sl_trigger_by or "LastPrice"

        async with self._lock:
            body, headers = self._prepare_private_request(payload)
            response = await self._account_client.post(
                "/v5/order/create",
                content=body,
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit order error: {data}")
        result = data.get("result", {})
        return OrderPlacementResult(
            order_id=result.get("orderId", ""),
            status=result.get("orderStatus", ""),
            qty=float(normalized_qty),
        )

    async def cancel_order(self, symbol: str, order_id: str) -> None:
        payload = {"category": "linear", "symbol": symbol, "orderId": order_id}
        async with self._lock:
            body, headers = self._prepare_private_request(payload)
            response = await self._account_client.post(
                "/v5/order/cancel",
                content=body,
                headers=headers,
            )
        response.raise_for_status()

    async def get_order_status(
        self, symbol: str, order_id: str
    ) -> Optional[OrderStatusInfo]:
        payload = {"category": "linear", "symbol": symbol, "orderId": order_id}
        params, headers = self._prepare_private_query(payload)
        async with self._lock:
            response = await self._account_client.get(
                "/v5/order/realtime",
                params=params,
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit order status error: {data}")
        result = data.get("result") or {}
        entries = result.get("list") or []
        if not entries:
            return None
        entry = entries[0]
        status_raw = entry.get("orderStatus") or ""
        avg_price = self._to_float(entry.get("avgPrice"))
        if avg_price == 0.0:
            avg_price = None
        cum_exec_qty = self._to_float(entry.get("cumExecQty"))
        if cum_exec_qty == 0.0:
            cum_exec_qty = None
        cum_exec_fee = self._to_float(entry.get("cumExecFee"))
        if cum_exec_fee == 0.0:
            cum_exec_fee = None
        updated_raw = entry.get("updatedTime") or entry.get("createdTime")
        updated_at: Optional[datetime] = None
        if isinstance(updated_raw, str) and updated_raw.isdigit():
            try:
                updated_at = datetime.fromtimestamp(
                    int(updated_raw) / 1000, tz=timezone.utc
                )
            except (OverflowError, ValueError):
                updated_at = None
        return OrderStatusInfo(
            status=status_raw,
            avg_price=avg_price,
            cum_exec_qty=cum_exec_qty,
            cum_exec_fee=cum_exec_fee,
            updated_at=updated_at,
        )

    async def get_order_status_raw(
        self, symbol: str, order_id: str
    ) -> Optional[dict[str, Any]]:
        payload = {"category": "linear", "symbol": symbol, "orderId": order_id}
        params, headers = self._prepare_private_query(payload)
        async with self._lock:
            response = await self._account_client.get(
                "/v5/order/realtime",
                params=params,
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit order status error: {data}")
        result = data.get("result") or {}
        entries = result.get("list") or []
        if not entries:
            return None
        return entries[0]

    async def fetch_positions(
        self, *, settle_coin: str | None = "USDT", symbol: str | None = None
    ) -> List[dict[str, Any]]:
        payload = {"category": "linear", "settleCoin": settle_coin, "symbol": symbol}
        response = await self._private_get("/v5/position/list", payload)
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit position error: {data}")
        result = data.get("result") or {}
        entries = result.get("list") or []
        positions: List[dict[str, Any]] = []
        for entry in entries:
            size = self._to_float(entry.get("size"))
            if size <= 0:
                continue
            entry_price = self._to_optional_float(entry.get("entryPrice"))
            if entry_price is None or entry_price == 0.0:
                entry_price = self._to_optional_float(entry.get("avgPrice"))
            mark_price = self._to_optional_float(entry.get("markPrice"))
            side_raw = (entry.get("side") or "").lower()
            side = (
                "long"
                if side_raw == "buy"
                else "short" if side_raw == "sell" else "flat"
            )
            unrealized = self._to_optional_float(entry.get("unrealisedPnl"))
            notional = self._to_optional_float(entry.get("positionValue"))
            leverage = self._to_optional_float(entry.get("leverage"))
            liquidation = self._to_optional_float(entry.get("liqPrice"))
            updated_at = entry.get("updatedTime") or entry.get("createdTime")
            updated_iso: str | None = None
            if isinstance(updated_at, str) and updated_at.isdigit():
                try:
                    updated_iso = datetime.fromtimestamp(
                        int(updated_at) / 1000, tz=timezone.utc
                    ).isoformat()
                except (OverflowError, ValueError):
                    updated_iso = None

            pnl_pct = None
            if entry_price and mark_price and entry_price > 0:
                diff = (mark_price - entry_price) / entry_price
                if side == "short":
                    diff = (entry_price - mark_price) / entry_price
                pnl_pct = diff * 100

            position = {
                "symbol": entry.get("symbol"),
                "side": side,
                "size": size,
                "entry_price": entry_price,
                "mark_price": mark_price,
                "notional_usdt": notional,
                "leverage": leverage,
                "position_idx": entry.get("positionIdx"),
                "unrealized_pnl": unrealized,
                "unrealized_pnl_pct": pnl_pct,
                "liquidation_price": liquidation or None,
                "take_profit": self._to_float(entry.get("takeProfit")) or None,
                "stop_loss": self._to_float(entry.get("stopLoss")) or None,
                "updated_at": updated_iso,
            }
            positions.append(position)
        return positions

    async def fetch_wallet_balance(
        self, coin: str = "USDT", account_type: str = "UNIFIED"
    ) -> dict[str, float]:
        payload: dict[str, Any] = {"accountType": account_type}
        if coin:
            payload["coin"] = coin
        response = await self._private_get("/v5/account/wallet-balance", payload)
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit wallet balance error: {data}")
        result = data.get("result") or {}
        lists = result.get("list") or []
        total_equity = 0.0
        available = 0.0
        wallet = 0.0
        for entry in lists:
            total_equity = max(total_equity, self._to_float(entry.get("totalEquity")))
            coins = entry.get("coin") or []
            for item in coins:
                if coin and item.get("coin") != coin:
                    continue
                wallet = self._to_float(item.get("walletBalance"), wallet)
                available = self._to_float(item.get("availableToWithdraw"), available)
        return {
            "total_equity": total_equity,
            "wallet_balance": wallet,
            "available_to_withdraw": available,
        }

    async def fetch_wallet_balance_raw(
        self, coin: str = "USDT", account_type: str = "UNIFIED"
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"accountType": account_type}
        if coin:
            payload["coin"] = coin
        response = await self._private_get("/v5/account/wallet-balance", payload)
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit wallet balance error: {data}")
        return data

    async def fetch_executions(
        self,
        *,
        symbol: str | None = None,
        start_time: datetime | int | float | None = None,
        end_time: datetime | int | float | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> Tuple[list[dict[str, Any]], Optional[str]]:
        decoded_cursor = self._decode_cursor(cursor)
        payload: Dict[str, Any] = {
            "category": "linear",
            "symbol": symbol,
            "limit": limit,
        }
        if decoded_cursor is not None:
            payload["cursor"] = decoded_cursor
        start_ms = self._to_milliseconds(start_time)
        end_ms = self._to_milliseconds(end_time)
        if start_ms is not None:
            payload["startTime"] = start_ms
        if end_ms is not None:
            payload["endTime"] = end_ms

        response = await self._private_get("/v5/execution/list", payload)
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit execution list error: {data}")

        result = data.get("result") or {}
        entries = result.get("list") or []
        normalized: list[dict[str, Any]] = []
        for entry in entries:
            normalized.append(
                {
                    "exec_id": entry.get("execId"),
                    "order_id": entry.get("orderId"),
                    "symbol": entry.get("symbol"),
                    "side": entry.get("side"),
                    "order_type": entry.get("orderType"),
                    "exec_type": entry.get("execType"),
                    "fee_currency": entry.get("execFeeCurrency"),
                    "trade_time": self._timestamp_to_iso(entry.get("execTime")),
                    "price": self._to_float(entry.get("execPrice")),
                    "quantity": self._to_float(entry.get("execQty")),
                    "gross_value": self._to_float(entry.get("execValue")),
                    "fee": self._to_float(entry.get("execFee")),
                    "realized_pnl": self._to_float(entry.get("closedPnl")),
                }
            )

        return normalized, result.get("nextPageCursor")

    async def fetch_closed_pnl(
        self,
        *,
        symbol: str | None = None,
        start_time: datetime | int | float | None = None,
        end_time: datetime | int | float | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> Tuple[list[dict[str, Any]], Optional[str]]:
        decoded_cursor = self._decode_cursor(cursor)
        payload: Dict[str, Any] = {
            "category": "linear",
            "symbol": symbol,
            "limit": limit,
        }
        if decoded_cursor is not None:
            payload["cursor"] = decoded_cursor
        start_ms = self._to_milliseconds(start_time)
        end_ms = self._to_milliseconds(end_time)
        if start_ms is not None:
            payload["startTime"] = start_ms
        if end_ms is not None:
            payload["endTime"] = end_ms

        response = await self._private_get("/v5/position/closed-pnl", payload)
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit closed PnL error: {data}")

        result = data.get("result") or {}
        entries = result.get("list") or []
        normalized: list[dict[str, Any]] = []
        for entry in entries:
            normalized.append(
                {
                    "symbol": entry.get("symbol"),
                    "side": entry.get("side"),
                    "order_id": entry.get("orderId"),
                    "position_idx": entry.get("positionIdx"),
                    "trade_time": self._timestamp_to_iso(entry.get("updatedTime")),
                    "closed_size": self._to_float(entry.get("closedSize")),
                    "avg_entry_price": self._to_float(entry.get("avgEntryPrice")),
                    "avg_exit_price": self._to_float(entry.get("avgExitPrice")),
                    "realized_pnl": self._to_float(entry.get("closedPnl")),
                    "cum_fee": self._to_float(entry.get("cumRealisedPnl"))
                    - self._to_float(entry.get("closedPnl")),
                }
            )

        return normalized, result.get("nextPageCursor")

    async def fetch_account_transactions(
        self,
        *,
        start_time: datetime | int | float | None = None,
        end_time: datetime | int | float | None = None,
        cursor: str | None = None,
        limit: int = 200,
    ) -> Tuple[list[dict[str, Any]], Optional[str]]:
        decoded_cursor = self._decode_cursor(cursor)
        payload: Dict[str, Any] = {
            "accountType": "UNIFIED",
            "limit": limit,
        }
        if decoded_cursor is not None:
            payload["cursor"] = decoded_cursor
        start_ms = self._to_milliseconds(start_time)
        end_ms = self._to_milliseconds(end_time)
        if start_ms is not None:
            payload["startTime"] = start_ms
        if end_ms is not None:
            payload["endTime"] = end_ms

        response = await self._private_get("/v5/account/transaction-log", payload)
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit transaction log error: {data}")

        result = data.get("result") or {}
        entries = result.get("list") or []
        normalized: list[dict[str, Any]] = []
        for entry in entries:
            tx_type_raw = entry.get("type")
            tx_type = (tx_type_raw or "").upper()
            if tx_type in IGNORED_TRANSACTION_TYPES:
                self._logger.debug(
                    "bybit_skip_transaction_type",
                    transaction_id=entry.get("id"),
                    type=tx_type,
                )
                continue
            sub_type_raw = entry.get("subType")
            sub_type = (sub_type_raw or "").upper() if sub_type_raw else None
            amount = self._to_optional_float(entry.get("change"))
            fee = self._to_optional_float(entry.get("fee"))
            normalized.append(
                {
                    "transaction_id": entry.get("id"),
                    "type": tx_type,
                    "sub_type": sub_type,
                    "symbol": entry.get("symbol"),
                    "reference_id": entry.get("tradeId") or entry.get("orderId"),
                    "amount": amount,
                    "fee": fee,
                    "currency": entry.get("currency"),
                    "wallet_type": entry.get("walletType"),
                    "trade_time": self._timestamp_to_iso(entry.get("createdTime")),
                }
            )

        return normalized, result.get("nextPageCursor")

    async def set_leverage(
        self, symbol: str, leverage: float, *, category: str = "linear"
    ) -> None:
        leverage_decimal = self._to_decimal(leverage, "1")
        leverage_str = self._decimal_to_str(leverage_decimal)
        payload = {
            "category": category,
            "symbol": symbol,
            "buyLeverage": leverage_str,
            "sellLeverage": leverage_str,
        }
        async with self._lock:
            body, headers = self._prepare_private_request(payload)
            response = await self._account_client.post(
                "/v5/position/set-leverage",
                content=body,
                headers=headers,
            )
        response.raise_for_status()
        data = response.json()
        if data.get("retCode") in (110043, "110043"):
            return
        if data.get("retCode") not in (0, "0"):
            raise RuntimeError(f"Bybit leverage error: {data}")

    def _prepare_private_request(
        self, payload: Dict[str, Any]
    ) -> Tuple[str, Dict[str, str]]:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        headers = self._build_auth_headers(body)
        return body, headers

    def _prepare_private_query(
        self, params: Dict[str, Any]
    ) -> Tuple[str, Dict[str, str]]:
        filtered_items = {
            key: value for key, value in params.items() if value is not None
        }
        if not filtered_items:
            encoded_query = ""
        else:
            sorted_items = sorted(filtered_items.items(), key=lambda item: item[0])
            encoded_query = urllib.parse.urlencode(
                sorted_items, doseq=True, quote_via=urllib.parse.quote
            )
        headers = self._build_auth_headers(encoded_query)
        return encoded_query, headers

    async def _private_get(
        self, path: str, payload: Dict[str, Any], *, max_attempts: int = 5
    ) -> httpx.Response:
        attempt = 0
        while True:
            query, headers = self._prepare_private_query(payload)
            url = path if not query else f"{path}?{query}"
            try:
                async with self._lock:
                    response = await self._account_client.get(url, headers=headers)
                return response
            except httpx.TimeoutException:
                attempt += 1
                if attempt >= max_attempts:
                    raise
                self._logger.warning(
                    "bybit_private_timeout_retry",
                    path=path,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
                await asyncio.sleep(min(2.0 * attempt, 5.0))

    def _build_auth_headers(self, body: str) -> Dict[str, str]:
        api_key = self._settings.bybit_api_key
        api_secret = self._settings.bybit_api_secret
        if not api_key or not api_secret:
            raise RuntimeError("Bybit API credentials are not configured")

        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        signature_payload = f"{timestamp}{api_key}{recv_window}{body}"
        signature = hmac.new(
            api_secret.encode("utf-8"),
            signature_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
        }

    @staticmethod
    def _to_decimal(value: Any, default: str = "0") -> Decimal:
        try:
            raw = value if value is not None else default
            return Decimal(str(raw))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def _decimal_to_str(value: Decimal) -> str:
        normalized = value.normalize()
        string = format(normalized, "f")
        if "." in string:
            string = string.rstrip("0").rstrip(".")
        return string or "0"
