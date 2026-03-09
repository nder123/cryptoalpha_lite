from __future__ import annotations

"""Historical replay helper for RLTrainer.

This script replays stored MarketSnapshot / Trade events into the event bus
so that RLStateBuilder and RLTrainer can backfill experience for 30-day
windows ahead of live testing.
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List

import json

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.domain import streams
from app.domain.events import ExecutionReport, MarketSnapshot, TradeDirective
from app.infrastructure.event_bus import event_bus

LOGGER = get_logger(__name__)


async def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(f"Replay file not found: {path}")
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data.append(json.loads(line))
    return data


async def _publish_snapshots(bus, snapshots: List[Dict[str, Any]], pace_seconds: float) -> None:
    for payload in snapshots:
        snapshot = MarketSnapshot.model_validate(payload)
        await bus.publish(streams.MARKET_SNAPSHOTS, snapshot)
        await asyncio.sleep(pace_seconds)


async def _publish_directives(bus, directives: List[Dict[str, Any]], pace_seconds: float) -> None:
    for payload in directives:
        directive = TradeDirective.model_validate(payload)
        await bus.publish(streams.CTOAI_DIRECTIVES, directive)
        await asyncio.sleep(pace_seconds)


async def _publish_execution_reports(bus, reports: List[Dict[str, Any]], pace_seconds: float) -> None:
    for payload in reports:
        report = ExecutionReport.model_validate(payload)
        await bus.publish(streams.EXECUTION_REPORTS, report)
        await asyncio.sleep(pace_seconds)


async def replay_history(snapshots_file: Path, directives_file: Path, executions_file: Path, pace_seconds: float) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    snapshots = await _load_jsonl(snapshots_file)
    directives = await _load_jsonl(directives_file)
    executions = await _load_jsonl(executions_file)

    LOGGER.info(
        "rl_replay_start",
        snapshots=len(snapshots),
        directives=len(directives),
        executions=len(executions),
        pace_seconds=pace_seconds,
    )

    async with event_bus() as bus:
        await asyncio.gather(
            _publish_snapshots(bus, snapshots, pace_seconds),
            _publish_directives(bus, directives, pace_seconds),
            _publish_execution_reports(bus, executions, pace_seconds),
        )

    LOGGER.info("rl_replay_complete")


async def wipe_rl_caches() -> None:
    settings = get_settings()
    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    try:
        pattern_keys = ["rl_state_cache:*", "rl_metrics:*"]
        for pattern in pattern_keys:
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor=cursor, match=pattern, count=200)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
        LOGGER.info("rl_caches_cleared")
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay market history for RL training")
    parser.add_argument("--snapshots", type=Path, required=True, help="Path to MarketSnapshot JSONL file")
    parser.add_argument("--directives", type=Path, required=True, help="Path to TradeDirective JSONL file")
    parser.add_argument("--executions", type=Path, required=True, help="Path to ExecutionReport JSONL file")
    parser.add_argument(
        "--pace-seconds",
        type=float,
        default=0.2,
        help="Delay between published events (default: 0.2s)",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Clear RL caches (state + metrics) before replay",
    )

    args = parser.parse_args()

    asyncio.run(_main_async(args))


async def _main_async(args: argparse.Namespace) -> None:
    if args.wipe:
        await wipe_rl_caches()
    await replay_history(args.snapshots, args.directives, args.executions, args.pace_seconds)


if __name__ == "__main__":
    main()
