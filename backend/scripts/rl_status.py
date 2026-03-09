from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime

import redis.asyncio as redis

from app.core.config import get_settings

POLICY_KEY = "rl_policy:latest"
ACTIVE_VERSION_KEY = "rl_policy:active_version"
POLICY_BY_VERSION_PREFIX = "rl_policy:by_version:"
EXPERIENCE_KEY = "rl_trainer:experience_buffer"
LATEST_METRICS_KEY = "rl_metrics:latest"
PERFORMANCE_KEY = "rl_metrics:performance"


def _parse_timestamp(raw: str | None) -> str:
    if not raw:
        return "n/a"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    return dt.isoformat()


async def _gather_status() -> dict[str, object]:
    settings = get_settings()
    client = redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
    try:
        experience_len = await client.llen(EXPERIENCE_KEY)
        first_raw = await client.lindex(EXPERIENCE_KEY, 0)
        last_raw = await client.lindex(EXPERIENCE_KEY, -1)
        metrics_raw = await client.get(LATEST_METRICS_KEY)
        performance_raw = await client.get(PERFORMANCE_KEY)
        policy_raw = await client.get(POLICY_KEY)
        active_version = await client.get(ACTIVE_VERSION_KEY)
        active_policy_raw = None
        if active_version:
            active_policy_raw = await client.get(
                f"{POLICY_BY_VERSION_PREFIX}{active_version}"
            )
    finally:
        await client.aclose()

    def _decode_experience(raw: str | None) -> dict[str, object] | None:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"error": "invalid json"}
        if timestamp := payload.get("timestamp"):
            payload["timestamp"] = _parse_timestamp(timestamp)
        return payload

    status: dict[str, object] = {
        "experience_count": experience_len,
        "experience_oldest": _decode_experience(first_raw),
        "experience_latest": _decode_experience(last_raw),
        "active_policy_version": active_version,
    }

    if metrics_raw:
        try:
            status["latest_metrics"] = json.loads(metrics_raw)
        except json.JSONDecodeError:
            status["latest_metrics"] = {"error": "invalid json", "raw": metrics_raw}
    else:
        status["latest_metrics"] = None

    if performance_raw:
        try:
            status["performance_tracker"] = json.loads(performance_raw)
        except json.JSONDecodeError:
            status["performance_tracker"] = {
                "error": "invalid json",
                "raw": performance_raw,
            }
    else:
        status["performance_tracker"] = None

    if policy_raw:
        try:
            policy = json.loads(policy_raw)
        except json.JSONDecodeError:
            status["policy"] = {"error": "invalid json", "raw": policy_raw}
        else:
            policy_summary = {
                "version": policy.get("version"),
                "architecture": policy.get("architecture"),
                "threshold": policy.get("threshold"),
                "input_size": policy.get("input_size"),
                "hidden_size": policy.get("hidden_size"),
                "action_size": policy.get("action_size"),
            }
            status["policy"] = policy_summary
    else:
        status["policy"] = None

    if active_policy_raw:
        try:
            active_policy = json.loads(active_policy_raw)
        except json.JSONDecodeError:
            status["active_policy"] = {
                "error": "invalid json",
                "raw": active_policy_raw,
            }
        else:
            active_policy_summary = {
                "version": active_policy.get("version"),
                "architecture": active_policy.get("architecture"),
                "threshold": active_policy.get("threshold"),
                "input_size": active_policy.get("input_size"),
                "hidden_size": active_policy.get("hidden_size"),
                "action_size": active_policy.get("action_size"),
            }
            status["active_policy"] = active_policy_summary
    else:
        status["active_policy"] = None

    return status


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Inspect RL trainer state in Redis")
    parser.parse_args(argv)
    status = asyncio.run(_gather_status())
    print(json.dumps(status, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
