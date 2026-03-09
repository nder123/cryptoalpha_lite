#!/usr/bin/env python3

import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional

_KV_RE = re.compile(r"([a-zA-Z0-9_]+)=([^\s]+)")


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if value.lower() in {"n/a", "none", "nan"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _kv_pairs(line: str) -> dict[str, str]:
    return {k: v for k, v in _KV_RE.findall(line)}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _emit_alert(
    message: str,
    alert_cmd: Optional[str],
    min_interval_seconds: float,
    last_sent_ts: dict[str, float],
    key: str,
) -> None:
    now = time.time()
    prev = last_sent_ts.get(key)
    if prev is not None and (now - prev) < min_interval_seconds:
        return
    last_sent_ts[key] = now

    line = f"{_now_utc()}  ALERT  {message}"
    print(line, flush=True)

    if not alert_cmd:
        return
    env = os.environ.copy()
    env["RL_ALERT_MESSAGE"] = message
    env["RL_ALERT_LINE"] = line
    cmd = shlex.split(alert_cmd)
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip() or "n/a"
        print(
            f"{_now_utc()}  alert_cmd_error  rc={proc.returncode}  stderr={stderr}",
            flush=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--helper",
        default=os.path.join(os.path.dirname(__file__), "rl_baseline_helper.py"),
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--since", default=None)
    parser.add_argument("--hours", type=float, default=None)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--no-change-limit", type=int, default=5)
    parser.add_argument("--sharpe-floor", type=float, default=-0.60)
    parser.add_argument("--drawdown-floor", type=float, default=-0.60)
    parser.add_argument("--alert-cooldown-sec", type=float, default=300.0)
    parser.add_argument(
        "--alert-cmd",
        default=None,
        help="Shell command invoked on alert; receives RL_ALERT_MESSAGE and RL_ALERT_LINE env vars.",
    )
    args = parser.parse_args()

    cmd = [
        args.python,
        "-u",
        args.helper,
        "--api-base",
        args.api_base,
        "--interval",
        str(args.interval),
        "--min-trades",
        str(args.min_trades),
        "--top",
        str(args.top),
        "--timeout",
        str(args.timeout),
    ]
    if args.since:
        cmd.extend(["--since", args.since])
    if args.hours is not None:
        cmd.extend(["--hours", str(float(args.hours))])

    print(f"{_now_utc()}  watchdog_start  cmd={shlex.join(cmd)}", flush=True)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    no_change_streak = 0
    last_sent_ts: dict[str, float] = {}
    last_policy_version: Optional[str] = None

    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")
            print(line, flush=True)

            if line.startswith("report_skipped  reason=no_change"):
                no_change_streak += 1
                if no_change_streak >= args.no_change_limit:
                    _emit_alert(
                        message=(
                            f"no_change_streak={no_change_streak} "
                            f"threshold={args.no_change_limit} interval_sec={args.interval}"
                        ),
                        alert_cmd=args.alert_cmd,
                        min_interval_seconds=args.alert_cooldown_sec,
                        last_sent_ts=last_sent_ts,
                        key="no_change",
                    )
                continue

            # Any non-no_change signal resets the streak.
            no_change_streak = 0

            if line.startswith("rl_status"):
                kv = _kv_pairs(line)
                policy_version = kv.get("policy_version")
                if policy_version and policy_version.lower() not in {"n/a", "none"}:
                    if last_policy_version is None:
                        last_policy_version = policy_version
                    elif policy_version != last_policy_version:
                        _emit_alert(
                            message=f"policy_version_changed  prev={last_policy_version}  next={policy_version}",
                            alert_cmd=args.alert_cmd,
                            min_interval_seconds=args.alert_cooldown_sec,
                            last_sent_ts=last_sent_ts,
                            key="policy_version_changed",
                        )
                        last_policy_version = policy_version
                continue

            if line.startswith("rl_status_error"):
                _emit_alert(
                    message=line,
                    alert_cmd=args.alert_cmd,
                    min_interval_seconds=args.alert_cooldown_sec,
                    last_sent_ts=last_sent_ts,
                    key="rl_status_error",
                )
                continue

            if line.startswith("window_status"):
                kv = _kv_pairs(line)
                ready = kv.get("ready")
                policy_version = kv.get("policy_version")
                new_trades = kv.get("new_trades")
                min_trades = kv.get("min_trades")
                if (
                    ready == "true"
                    and policy_version
                    and policy_version.lower() not in {"n/a", "none"}
                ):
                    _emit_alert(
                        message=(
                            f"policy_ready  policy_version={policy_version}  "
                            f"new_trades={new_trades or 'n/a'}  min_trades={min_trades or 'n/a'}"
                        ),
                        alert_cmd=args.alert_cmd,
                        min_interval_seconds=args.alert_cooldown_sec,
                        last_sent_ts=last_sent_ts,
                        key=f"policy_ready:{policy_version}:{args.since or ''}:{args.min_trades}",
                    )
                continue

            if line.startswith("latest_metrics"):
                kv = _kv_pairs(line)
                sharpe = _to_float(kv.get("sharpe_like"))
                drawdown = _to_float(kv.get("max_drawdown"))

                if sharpe is not None and sharpe <= args.sharpe_floor:
                    _emit_alert(
                        message=f"sharpe_like={sharpe:.6f} <= floor={args.sharpe_floor:.6f}",
                        alert_cmd=args.alert_cmd,
                        min_interval_seconds=args.alert_cooldown_sec,
                        last_sent_ts=last_sent_ts,
                        key="sharpe_floor",
                    )

                if drawdown is not None and drawdown <= args.drawdown_floor:
                    _emit_alert(
                        message=f"max_drawdown={drawdown:.6f} <= floor={args.drawdown_floor:.6f}",
                        alert_cmd=args.alert_cmd,
                        min_interval_seconds=args.alert_cooldown_sec,
                        last_sent_ts=last_sent_ts,
                        key="drawdown_floor",
                    )

        return_code = proc.wait(timeout=2)
        print(f"{_now_utc()}  watchdog_exit  helper_rc={return_code}", flush=True)
        return return_code
    except KeyboardInterrupt:
        print(f"{_now_utc()}  watchdog_stop  reason=keyboard_interrupt", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
