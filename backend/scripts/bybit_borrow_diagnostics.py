from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.exchange.bybit import BybitClient


def _pick_first(d: dict[str, Any], keys: list[str]) -> object | None:
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return None


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _run(coin: str, account_type: str, dump_raw: bool) -> int:
    client = BybitClient()
    try:
        raw = await client.fetch_wallet_balance_raw(
            coin=coin, account_type=account_type
        )
        if dump_raw:
            print(json.dumps(raw, indent=2, sort_keys=True))

        result = raw.get("result") or {}
        lists = result.get("list") or []
        entry0 = lists[0] if lists else {}
        coins: list[dict[str, Any]] = []
        for entry in lists:
            for item in entry.get("coin") or []:
                if coin and item.get("coin") != coin:
                    continue
                coins.append(item)

        summary: dict[str, Any] = {
            "account_type": account_type,
            "coin": coin,
            "time": datetime.now(timezone.utc).isoformat(),
            "coins_matched": len(coins),
        }

        if coins:
            item = coins[0]
            summary.update(
                {
                    "walletBalance": _to_float(item.get("walletBalance")),
                    "availableToWithdraw": _to_float(item.get("availableToWithdraw")),
                    "availableToBorrow": _to_float(
                        _pick_first(item, ["availableToBorrow", "availableToBorrowed"])
                    ),
                    "borrowAmount": _to_float(
                        _pick_first(
                            item, ["borrowAmount", "borrowedAmount", "totalBorrow"]
                        )
                    ),
                    "liability": _to_float(
                        _pick_first(item, ["liability", "totalLiability"])
                    ),
                    "unrealisedPnl": _to_float(
                        _pick_first(item, ["unrealisedPnl", "unrealizedPnl"])
                    ),
                    "cumRealisedPnl": _to_float(
                        _pick_first(item, ["cumRealisedPnl", "cumRealizedPnl"])
                    ),
                    "coin_item_keys": sorted(list(item.keys())),
                }
            )

        # Some UNIFIED fields live at the account-entry level (result.list[*]) rather than inside coin[].
        if entry0:
            summary.update(
                {
                    "entry_totalEquity": _to_float(
                        _pick_first(entry0, ["totalEquity"])
                    ),
                    "entry_totalWalletBalance": _to_float(
                        _pick_first(entry0, ["totalWalletBalance"])
                    ),
                    "entry_totalMarginBalance": _to_float(
                        _pick_first(entry0, ["totalMarginBalance"])
                    ),
                    "entry_totalAvailableBalance": _to_float(
                        _pick_first(entry0, ["totalAvailableBalance"])
                    ),
                    "entry_totalLiability": _to_float(
                        _pick_first(entry0, ["totalLiability", "totalLiabilityValue"])
                    ),
                    "entry_totalBorrow": _to_float(
                        _pick_first(entry0, ["totalBorrow", "totalBorrowAmount"])
                    ),
                    "entry_keys": sorted(list(entry0.keys())),
                }
            )

        # Positions snapshot
        positions = await client.fetch_positions()

        print("\n=== WALLET SUMMARY ===")
        print(json.dumps(summary, indent=2, sort_keys=True))

        print("\n=== OPEN POSITIONS (normalized) ===")
        print(json.dumps(positions, indent=2, sort_keys=True))

        return 0
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Bybit UNIFIED borrow/liability diagnostics"
    )
    parser.add_argument("--coin", default="USDT")
    parser.add_argument("--account-type", default="UNIFIED")
    parser.add_argument(
        "--dump-raw",
        action="store_true",
        help="Print raw /wallet-balance response JSON",
    )
    parser.add_argument(
        "--mode",
        choices=["summary", "full"],
        default="summary",
        help="summary=wallet+positions only; full=also include recent executions",
    )
    parser.add_argument("--positions-limit", type=int, default=20)
    parser.add_argument("--executions-hours", type=float, default=6.0)
    parser.add_argument("--executions-limit", type=int, default=200)
    args = parser.parse_args(argv)

    async def _entry() -> int:
        client = BybitClient()
        try:
            raw = await client.fetch_wallet_balance_raw(
                coin=args.coin, account_type=args.account_type
            )
            if args.dump_raw:
                print(json.dumps(raw, indent=2, sort_keys=True))

            result = raw.get("result") or {}
            lists = result.get("list") or []
            entry0 = lists[0] if lists else {}
            coins: list[dict[str, Any]] = []
            for entry in lists:
                for item in entry.get("coin") or []:
                    if args.coin and item.get("coin") != args.coin:
                        continue
                    coins.append(item)

            summary: dict[str, Any] = {
                "account_type": args.account_type,
                "coin": args.coin,
                "time": datetime.now(timezone.utc).isoformat(),
                "coins_matched": len(coins),
            }
            if coins:
                item = coins[0]
                summary.update(
                    {
                        "walletBalance": _to_float(item.get("walletBalance")),
                        "availableToWithdraw": _to_float(
                            item.get("availableToWithdraw")
                        ),
                        "availableToBorrow": _to_float(
                            _pick_first(
                                item, ["availableToBorrow", "availableToBorrowed"]
                            )
                        ),
                        "borrowAmount": _to_float(
                            _pick_first(
                                item, ["borrowAmount", "borrowedAmount", "totalBorrow"]
                            )
                        ),
                        "liability": _to_float(
                            _pick_first(item, ["liability", "totalLiability"])
                        ),
                        "unrealisedPnl": _to_float(
                            _pick_first(item, ["unrealisedPnl", "unrealizedPnl"])
                        ),
                        "cumRealisedPnl": _to_float(
                            _pick_first(item, ["cumRealisedPnl", "cumRealizedPnl"])
                        ),
                        "coin_item_keys": sorted(list(item.keys())),
                    }
                )
            if entry0:
                summary.update(
                    {
                        "entry_totalEquity": _to_float(
                            _pick_first(entry0, ["totalEquity"])
                        ),
                        "entry_totalWalletBalance": _to_float(
                            _pick_first(entry0, ["totalWalletBalance"])
                        ),
                        "entry_totalMarginBalance": _to_float(
                            _pick_first(entry0, ["totalMarginBalance"])
                        ),
                        "entry_totalAvailableBalance": _to_float(
                            _pick_first(entry0, ["totalAvailableBalance"])
                        ),
                        "entry_totalLiability": _to_float(
                            _pick_first(
                                entry0, ["totalLiability", "totalLiabilityValue"]
                            )
                        ),
                        "entry_totalBorrow": _to_float(
                            _pick_first(entry0, ["totalBorrow", "totalBorrowAmount"])
                        ),
                        "entry_keys": sorted(list(entry0.keys())),
                    }
                )

            positions = await client.fetch_positions()
            if args.positions_limit and args.positions_limit > 0:
                positions = list(positions)[: args.positions_limit]

            print("\n=== WALLET SUMMARY ===")
            print(json.dumps(summary, indent=2, sort_keys=True))
            print("\n=== OPEN POSITIONS (normalized) ===")
            print(json.dumps(positions, indent=2, sort_keys=True))

            if args.mode == "full":
                now = datetime.now(timezone.utc)
                executions, _ = await client.fetch_executions(
                    start_time=now - timedelta(hours=float(args.executions_hours)),
                    end_time=now,
                    limit=int(args.executions_limit),
                )
                print(
                    f"\n=== LAST EXECUTIONS ({args.executions_hours}h, normalized) ==="
                )
                print(json.dumps(executions, indent=2, sort_keys=True))

            return 0
        finally:
            await client.close()

    raise SystemExit(asyncio.run(_entry()))


if __name__ == "__main__":
    main()
