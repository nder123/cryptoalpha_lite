from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.exchange.bybit import BybitClient


async def _run(symbol: str, order_id: str) -> int:
    client = BybitClient()
    try:
        entry = await client.get_order_status_raw(symbol=symbol, order_id=order_id)
        print(json.dumps(entry, indent=2, sort_keys=True))
        return 0
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Dump raw /v5/order/realtime entry for an order")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--order-id", required=True)
    args = parser.parse_args(argv)

    raise SystemExit(asyncio.run(_run(args.symbol.upper(), args.order_id)))


if __name__ == "__main__":
    main()
