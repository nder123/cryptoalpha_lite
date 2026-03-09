#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Optional

_TRADES_COLS: list[str] = [
    "version",
    "first_seen",
    "last_seen",
    "trades",
    "win_rate",
    "avg_pnl_pct",
    "p50_pnl_pct",
    "p90_pnl_pct",
    "min_pnl_pct",
    "max_pnl_pct",
    "sum_pnl_pct",
    "sharpe_like",
    "max_drawdown",
]


def _read_json(url: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Non-dict JSON response")
    return data


def _fmt_dt(value: Any) -> str:
    if not value:
        return "n/a"
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value)).isoformat(timespec="seconds")
        except Exception:
            return str(value)
    if isinstance(value, str):
        return value
    return str(value)


def _get_in(dct: dict[str, Any], *keys: str) -> Any:
    cur: Any = dct
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _parse_iso_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        # Handle both "...Z" and "+00:00" forms.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_trades_row(line: str) -> dict[str, str]:
    # rl_snapshots_report.py prints columns separated by at least two spaces.
    # We must not rely on fixed widths because version strings can exceed the
    # nominal width and shift subsequent columns.
    parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
    out: dict[str, str] = {}
    for idx, col in enumerate(_TRADES_COLS):
        if idx < len(parts):
            out[col] = parts[idx]
    return out


def _print_rl_status(api_base: str, timeout_seconds: float) -> dict[str, Any]:
    url = api_base.rstrip("/") + "/api/rl/status"
    try:
        status = _read_json(url, timeout_seconds=timeout_seconds)
    except urllib.error.URLError as exc:
        print(f"rl_status_error  url={url}  error={exc}")
        return {}
    except Exception as exc:  # noqa: BLE001
        print(f"rl_status_error  url={url}  error={exc}")
        return {}

    policy = status.get("policy")
    policy_version = policy.get("version") if isinstance(policy, dict) else None
    policy_arch = policy.get("architecture") if isinstance(policy, dict) else None
    policy_threshold = policy.get("threshold") if isinstance(policy, dict) else None
    policy_updated_at = status.get("policy_updated_at")

    latest_metrics = status.get("latest_metrics")
    latest_metrics_ts = None
    total_trades = None
    losses_last_window = None
    loss_window_size = None
    win_rate = None
    sharpe_like = None
    max_drawdown = None
    max_drawdown_window = None
    last_pnl_pct = None
    last_pnl_pct_used = None
    last_reward = None
    if isinstance(latest_metrics, dict):
        latest_metrics_ts = latest_metrics.get("timestamp")
        total_trades = latest_metrics.get("total_trades")
        losses_last_window = latest_metrics.get("losses_last_window")
        loss_window_size = latest_metrics.get("loss_window_size")
        win_rate = latest_metrics.get("win_rate")
        # API uses sharpe_ratio naming.
        sharpe_like = latest_metrics.get("sharpe_like")
        if sharpe_like is None:
            sharpe_like = latest_metrics.get("sharpe_ratio")
        max_drawdown = latest_metrics.get("max_drawdown")
        max_drawdown_window = latest_metrics.get("max_drawdown_window")
        last_pnl_pct = latest_metrics.get("last_trade_pnl_pct")
        last_pnl_pct_used = latest_metrics.get("last_trade_pnl_pct_used")
        last_reward = latest_metrics.get("last_trade_reward")

    recent_closed = status.get("recent_closed")
    last_closed_at = None
    last_duration = None
    if isinstance(recent_closed, list) and recent_closed:
        best_dt: Optional[datetime] = None
        best_item: Optional[dict[str, Any]] = None
        for item in recent_closed:
            if not isinstance(item, dict):
                continue
            dt = _parse_iso_dt(item.get("closed_at"))
            if dt is None:
                continue
            if best_dt is None or dt > best_dt:
                best_dt = dt
                best_item = item
        if best_item is not None:
            last_closed_at = best_item.get("closed_at")
            last_duration = best_item.get("duration_seconds")

    autopilot = status.get("autopilot")
    ap_blocked = None
    ap_reason = None
    if isinstance(autopilot, dict):
        ap_blocked = autopilot.get("blocked")
        ap_reason = autopilot.get("blocked_reason")

    print(
        "rl_status  "
        f"policy_version={policy_version or 'n/a'}  "
        f"arch={policy_arch or 'n/a'}  "
        f"thr={(f'{float(policy_threshold):.3f}' if policy_threshold is not None else 'n/a')}  "
        f"policy_updated_at={_fmt_dt(policy_updated_at)}  "
        f"total_trades={total_trades if total_trades is not None else 'n/a'}  "
        f"losses_last_window={losses_last_window if losses_last_window is not None else 'n/a'}  "
        f"loss_window_size={loss_window_size if loss_window_size is not None else 'n/a'}"
    )
    print(
        "last_trade  "
        f"closed_at={_fmt_dt(last_closed_at)}  "
        f"duration_s={last_duration if last_duration is not None else 'n/a'}  "
        f"pnl_pct={last_pnl_pct if last_pnl_pct is not None else 'n/a'}  "
        f"pnl_used={last_pnl_pct_used if last_pnl_pct_used is not None else 'n/a'}  "
        f"reward={last_reward if last_reward is not None else 'n/a'}"
    )
    print(
        "latest_metrics  "
        f"ts={_fmt_dt(latest_metrics_ts)}  "
        f"losses_last_window={losses_last_window if losses_last_window is not None else 'n/a'}  "
        f"loss_window_size={loss_window_size if loss_window_size is not None else 'n/a'}  "
        f"win_rate={win_rate if win_rate is not None else 'n/a'}  "
        f"sharpe_like={sharpe_like if sharpe_like is not None else 'n/a'}  "
        f"max_drawdown={max_drawdown if max_drawdown is not None else 'n/a'}  "
        f"max_dd_win={max_drawdown_window if max_drawdown_window is not None else 'n/a'}"
    )
    if ap_blocked is not None:
        print(
            "autopilot  "
            f"blocked={ap_blocked}  "
            f"blocked_reason={ap_reason or 'n/a'}"
        )

    return {
        "policy_version": policy_version,
        "latest_metrics_ts": latest_metrics_ts,
        "last_closed_at": last_closed_at,
        "total_trades": total_trades,
    }


def _run_report(
    backend_dir: str,
    snapshots_path: str,
    min_trades: int,
    since: Optional[str],
    hours: Optional[float],
    clip_low: float,
    clip_high: float,
    sort_key: str,
    sort_order: str,
    top: int,
    current_policy_version: Optional[str],
) -> Optional[tuple[str, str]]:
    report_script = os.path.join(backend_dir, "scripts", "rl_snapshots_report.py")
    if not os.path.exists(report_script):
        raise FileNotFoundError(report_script)

    cmd = [
        sys.executable,
        report_script,
        "--mode",
        "trades",
        "--in",
        snapshots_path,
        "--min-trades",
        str(min_trades),
    ]

    if since:
        cmd.extend(["--since", str(since)])
    if hours is not None:
        cmd.extend(["--hours", str(float(hours))])

    cmd.extend(
        [
            "--clip-pnl-pct",
            str(clip_low),
            str(clip_high),
            "--sort",
            sort_key,
            "--sort-order",
            sort_order,
        ]
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        print(
            "report_error  "
            f"sort={sort_key}  "
            f"exit_code={proc.returncode}  "
            f"stderr={stderr or 'n/a'}"
        )
        return None

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        print(f"report_empty  sort={sort_key}")
        return None

    print(f"report_top  sort={sort_key}  order={sort_order}  top={top}")
    print(lines[0])
    for ln in lines[1 : 1 + top]:
        print(ln)

    current_trades: Optional[int] = None
    if current_policy_version:
        for ln in lines[1:]:
            try:
                parsed = _parse_trades_row(ln)
            except Exception:
                continue
            if parsed.get("version") != current_policy_version:
                continue
            trades_s = parsed.get("trades")
            if trades_s is None:
                continue
            try:
                current_trades = int(float(trades_s))
            except ValueError:
                current_trades = None
            break

    if current_policy_version and current_trades is not None:
        ready = current_trades >= int(min_trades)
        print(
            "window_status  "
            f"policy_version={current_policy_version}  "
            f"new_trades={current_trades}  "
            f"min_trades={int(min_trades)}  "
            f"ready={'true' if ready else 'false'}"
        )

    leader = None
    if len(lines) >= 2:
        try:
            parsed = _parse_trades_row(lines[1])
            leader_version = parsed.get("version")
            leader_value = parsed.get(sort_key)
            if leader_version and leader_value:
                leader = (leader_version, leader_value)
        except Exception:
            leader = None
    return leader


def _default_snapshots_path(backend_dir: str) -> str:
    candidates = [
        os.path.join(backend_dir, "rl_status_snapshots.jsonl"),
        os.path.join(backend_dir, "..", "backend", "rl_status_snapshots.jsonl"),
        os.path.join(
            os.path.expanduser("~"),
            "CascadeProjects",
            "cryptoalpha_lite",
            "backend",
            "rl_status_snapshots.jsonl",
        ),
    ]
    for p in candidates:
        p2 = os.path.abspath(p)
        if os.path.exists(p2):
            return p2
    return os.path.abspath(candidates[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5.0)

    parser.add_argument("--input", dest="snapshots_path", default=None)
    parser.add_argument("--min-trades", type=int, default=60)
    parser.add_argument("--clip-pnl-pct", nargs=2, type=float, default=[-0.3, 0.3])
    parser.add_argument("--since", default=None)
    parser.add_argument("--hours", type=float, default=None)
    parser.add_argument("--top", type=int, default=10)

    parser.add_argument("--interval", type=float, default=0.0)
    parser.add_argument("--once", action="store_true")

    args = parser.parse_args()

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    snapshots_path = args.snapshots_path or _default_snapshots_path(backend_dir)

    clip_low, clip_high = float(args.clip_pnl_pct[0]), float(args.clip_pnl_pct[1])

    last_seen_policy_version: Any = None
    last_seen_closed_at: Any = None
    last_seen_metrics_ts: Any = None
    last_seen_total_trades: Any = None
    last_seen_leader_p50: Optional[tuple[str, str]] = None
    last_seen_leader_dd: Optional[tuple[str, str]] = None

    def _tick() -> None:
        nonlocal last_seen_policy_version
        nonlocal last_seen_closed_at
        nonlocal last_seen_metrics_ts
        nonlocal last_seen_total_trades
        nonlocal last_seen_leader_p50
        nonlocal last_seen_leader_dd

        print(datetime.now().isoformat(timespec="seconds"))
        parsed = _print_rl_status(args.api_base, timeout_seconds=float(args.timeout))

        policy_version = parsed.get("policy_version")
        closed_at = parsed.get("last_closed_at")
        metrics_ts = parsed.get("latest_metrics_ts")
        total_trades = parsed.get("total_trades")

        status_changed = False
        if policy_version and policy_version != last_seen_policy_version:
            status_changed = True
        if closed_at and closed_at != last_seen_closed_at:
            status_changed = True
        if metrics_ts and metrics_ts != last_seen_metrics_ts:
            status_changed = True
        if total_trades is not None and total_trades != last_seen_total_trades:
            status_changed = True

        if policy_version:
            last_seen_policy_version = policy_version
        if closed_at:
            last_seen_closed_at = closed_at
        if metrics_ts:
            last_seen_metrics_ts = metrics_ts
        if total_trades is not None:
            last_seen_total_trades = total_trades

        if os.path.exists(snapshots_path):
            if (
                status_changed
                or last_seen_leader_p50 is None
                or last_seen_leader_dd is None
            ):
                leader_p50 = _run_report(
                    backend_dir=backend_dir,
                    snapshots_path=snapshots_path,
                    min_trades=int(args.min_trades),
                    since=args.since,
                    hours=args.hours,
                    clip_low=clip_low,
                    clip_high=clip_high,
                    sort_key="p50_pnl_pct",
                    sort_order="desc",
                    top=int(args.top),
                    current_policy_version=(
                        str(policy_version) if policy_version else None
                    ),
                )
                leader_dd = _run_report(
                    backend_dir=backend_dir,
                    snapshots_path=snapshots_path,
                    min_trades=int(args.min_trades),
                    since=args.since,
                    hours=args.hours,
                    clip_low=clip_low,
                    clip_high=clip_high,
                    sort_key="max_drawdown",
                    sort_order="desc",
                    top=int(args.top),
                    current_policy_version=(
                        str(policy_version) if policy_version else None
                    ),
                )

                leaders_changed = False
                if leader_p50 is not None and leader_p50 != last_seen_leader_p50:
                    leaders_changed = True
                if leader_dd is not None and leader_dd != last_seen_leader_dd:
                    leaders_changed = True

                if leader_p50 is not None:
                    last_seen_leader_p50 = leader_p50
                if leader_dd is not None:
                    last_seen_leader_dd = leader_dd

                if leaders_changed or leader_p50 is not None or leader_dd is not None:
                    p50_s = (
                        f"{leader_p50[0]}({leader_p50[1]})"
                        if leader_p50 is not None
                        else "n/a"
                    )
                    dd_s = (
                        f"{leader_dd[0]}({leader_dd[1]})"
                        if leader_dd is not None
                        else "n/a"
                    )
                    print(f"leaders  p50={p50_s}  max_drawdown={dd_s}")
            else:
                # No changes since previous tick - keep output compact.
                print("report_skipped  reason=no_change")
        else:
            print(f"snapshots_missing  path={snapshots_path}")
        print("")

    if args.once or args.interval <= 0:
        _tick()
        return

    while True:
        _tick()
        time.sleep(float(args.interval))


if __name__ == "__main__":
    main()
