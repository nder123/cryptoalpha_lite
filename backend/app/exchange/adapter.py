from dataclasses import dataclass


class ExchangeAdapter:
    pass


@dataclass
class ExchangeOrderStatus:
    status: str = ""
    avg_price: str | None = None
    cum_exec_qty: str | None = None
    cum_exec_fee: str | None = None


@dataclass
class ExchangeSubmitResult:
    exchange_order_id: str = ""
    status: str = ""
    qty: float = 0.0
