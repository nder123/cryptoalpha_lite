from __future__ import annotations

"""Utility to export event log streams into JSON Lines files."""

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

from sqlalchemy import Select, select

from app.infrastructure.database import db_session
from app.repositories.models import EventLog


async def _export_stream(stream: str, since: datetime, output: Path) -> int:
    stmt: Select[Tuple[Dict[str, object]]] = (
        select(EventLog.payload)
        .where(EventLog.stream == stream, EventLog.created_at >= since)
        .order_by(EventLog.created_at)
    )
    count = 0
    async with db_session() as session:
        result = await session.stream(stmt)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            async for row in result:
                payload = row[0]
                handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
                count += 1
    return count


async def _run_async(args: argparse.Namespace) -> None:
    horizon = datetime.now(timezone.utc) - timedelta(days=args.days)
    exports = {
        "market.snapshots": Path(args.snapshots),
        "ctoai.directives": Path(args.directives),
        "execution.reports": Path(args.executions),
    }
    for stream, path in exports.items():
        count = await _export_stream(stream, horizon, path)
        print(f"Exported {count} events from {stream} -> {path}")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export event streams to JSONL files")
    parser.add_argument("--days", type=int, default=30, help="How many days to export (default: 30)")
    parser.add_argument("--snapshots", type=str, default="/tmp/snapshots.jsonl", help="Output file for MarketSnapshot stream")
    parser.add_argument("--directives", type=str, default="/tmp/directives.jsonl", help="Output file for TradeDirective stream")
    parser.add_argument("--executions", type=str, default="/tmp/executions.jsonl", help="Output file for ExecutionReport stream")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    asyncio.run(_run_async(args))


if __name__ == "__main__":
    main()
