from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Response is not a JSON object")
    return payload


def _extract_policy_version(status: dict[str, Any]) -> str | None:
    policy = status.get("policy")
    if isinstance(policy, dict):
        version = policy.get("version")
        if isinstance(version, str) and version:
            return version
    return None


def _extract_total_trades(status: dict[str, Any]) -> int | None:
    latest = status.get("latest_metrics")
    if isinstance(latest, dict):
        value = latest.get("total_trades")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None


def _extract_closed_trades(
    status: dict[str, Any], limit: int = 50
) -> list[dict[str, Any]] | None:
    closed = status.get("closed_trades")
    if not isinstance(closed, list):
        closed = status.get("recent_closed")
    if not isinstance(closed, list):
        return None
    items: list[dict[str, Any]] = []
    for raw in closed[: max(limit, 0)]:
        if isinstance(raw, dict):
            items.append(raw)
    return items


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Periodically snapshot /api/rl/status into a JSONL file"
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/api/rl/status",
        help="RL status endpoint",
    )
    parser.add_argument(
        "--out",
        default=str(
            Path(
                "~/CascadeProjects/cryptoalpha_lite/backend/rl_status_snapshots.jsonl"
            ).expanduser()
        ),
        help="Output JSONL file",
    )
    parser.add_argument(
        "--interval", type=float, default=60.0, help="Seconds between snapshots"
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="HTTP timeout seconds"
    )
    parser.add_argument(
        "--once", action="store_true", help="Collect a single snapshot and exit"
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        collected_at = _utc_now_iso()
        record: dict[str, Any] = {
            "collected_at": collected_at,
            "source_url": args.url,
        }

        try:
            status = _fetch_json(args.url, timeout_seconds=args.timeout)
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            record["error"] = str(exc)
        else:
            record["status"] = status
            record["policy_version"] = _extract_policy_version(status)
            record["total_trades"] = _extract_total_trades(status)
            closed = _extract_closed_trades(status)
            if closed is not None:
                record["closed_trades"] = closed

        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        if args.once:
            break

        time.sleep(max(args.interval, 1.0))


if __name__ == "__main__":
    main()
