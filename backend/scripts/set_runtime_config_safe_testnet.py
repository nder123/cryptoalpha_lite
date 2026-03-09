from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _payload(denylist: list[str]) -> dict[str, Any]:
    return {
        # Safety rails
        "dry_run": True,
        "position_manager_use_market_exit": False,
        "position_manager_limit_exit_timeout_seconds": 20,
        "max_trades_per_day": 20,
        "max_daily_loss_usdt": 10,
        "max_consecutive_losses": 3,
        # Optional filters
        "symbol_denylist": denylist,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Set safe RuntimeConfig values for testnet warm-up"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--deny",
        action="append",
        default=[],
        help="Add symbol to denylist (repeatable). Example: --deny FARTCOINUSDT",
    )
    parser.add_argument(
        "--live", action="store_true", help="Set dry_run=false and tighter limits"
    )
    args = parser.parse_args(argv)

    denylist = [
        item.strip().upper() for item in (args.deny or []) if item and item.strip()
    ]

    payload = _payload(denylist)
    if args.live:
        payload.update(
            {
                "dry_run": False,
                "max_trades_per_day": 5,
                "max_daily_loss_usdt": 5,
                "max_consecutive_losses": 2,
            }
        )

    url = args.base_url.rstrip("/") + "/api/config/runtime"

    with httpx.Client(timeout=20.0) as client:
        resp = client.patch(url, json=payload)
        if resp.status_code >= 400:
            print(resp.text)
            raise SystemExit(2)
        print(json.dumps(resp.json(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
