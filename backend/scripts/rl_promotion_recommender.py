#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(url: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Non-dict JSON response")
    return data


def _is_promotable(api_base: str, policy_version: str, timeout_seconds: float) -> bool:
    if not policy_version:
        return False
    query = urllib.parse.urlencode({"version": policy_version})
    url = api_base.rstrip("/") + "/api/rl/policy/exists?" + query
    try:
        data = _read_json(url, timeout_seconds=timeout_seconds)
    except Exception:
        return False
    return bool(data.get("exists"))


def _parse_version_ts(policy_version: str) -> Optional[datetime]:
    if not policy_version:
        return None
    try:
        return datetime.fromisoformat(policy_version.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_trades_row(line: str) -> dict[str, str]:
    parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
    out: dict[str, str] = {}
    for idx, col in enumerate(_TRADES_COLS):
        if idx < len(parts):
            out[col] = parts[idx]
    return out


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if value.lower() in {"n/a", "none", "nan"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    if value.lower() in {"n/a", "none", "nan"}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _notify(title: str, body: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "--app-name", "CryptoAlpha", title, body],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return
    except Exception:
        return


def _emit_event(event: str, body: str) -> None:
    safe_body = (body or "").replace("\n", "\\n")
    print(f"{_now_utc()}  {event}  {safe_body}", flush=True)


def _default_snapshots_path(repo_root: Path) -> Path:
    candidates = [
        repo_root / "backend" / "rl_status_snapshots.jsonl",
        repo_root / "rl_status_snapshots.jsonl",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _run_trades_report(
    repo_root: Path,
    snapshots_path: Path,
    min_trades: int,
    since: Optional[str],
    hours: Optional[float],
) -> list[str]:
    report_script = repo_root / "backend" / "scripts" / "rl_snapshots_report.py"
    cmd = [
        sys.executable,
        str(report_script),
        "--mode",
        "trades",
        "--in",
        str(snapshots_path),
        "--min-trades",
        "1",
        "--sort",
        "max_drawdown",
        "--sort-order",
        "desc",
    ]
    if since:
        cmd.extend(["--since", since])
    if hours is not None:
        cmd.extend(["--hours", str(float(hours))])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip() or "n/a"
        raise RuntimeError(f"report_failed rc={proc.returncode} stderr={stderr}")
    return [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]


def _rows_by_version(lines: list[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for ln in lines[1:]:
        parsed = _parse_trades_row(ln)
        ver = parsed.get("version")
        if ver:
            out[ver] = parsed
    return out


@dataclass(frozen=True)
class WindowEval:
    window_name: str
    ready: bool
    current_trades: Optional[int]
    leader_version: Optional[str]
    leader_dd: Optional[float]
    current_dd: Optional[float]
    current_p50: Optional[float]
    current_avg: Optional[float]
    pass_primary: bool
    pass_secondary: bool


def _eval_window(
    window_name: str,
    lines: list[str],
    current_policy_version: str,
    min_trades: int,
    secondary_floor: float,
    baseline_policy_version: Optional[str] = None,
    primary_epsilon: float = 0.0,
) -> WindowEval:
    rows = _rows_by_version(lines)

    leader_version = None
    leader_dd = None
    # Pick leader among versions that are "ready" (trades >= min_trades) within this window.
    # We run rl_snapshots_report with --min-trades 1, so we must filter here.
    for ver, parsed in rows.items():
        trades = _to_int(parsed.get("trades"))
        dd = _to_float(parsed.get("max_drawdown"))
        if trades is None or dd is None:
            continue
        if trades < int(min_trades):
            continue
        if leader_dd is None or dd > leader_dd:
            leader_dd = dd
            leader_version = ver

    # If a baseline version is provided, try to use it as the comparator for primary.
    # This prevents window A from becoming unpassable due to a historical best leader_dd.
    if baseline_policy_version:
        baseline_row: Optional[dict[str, str]] = None
        baseline_row = rows.get(baseline_policy_version)
        baseline_dd = _to_float(
            baseline_row.get("max_drawdown") if baseline_row else None
        )
        if baseline_dd is not None:
            leader_version = baseline_policy_version
            leader_dd = baseline_dd

    current_row: Optional[dict[str, str]] = None
    current_row = rows.get(current_policy_version)

    current_trades = _to_int(current_row.get("trades") if current_row else None)
    current_dd = _to_float(current_row.get("max_drawdown") if current_row else None)
    current_p50 = _to_float(current_row.get("p50_pnl_pct") if current_row else None)
    current_avg = _to_float(current_row.get("avg_pnl_pct") if current_row else None)

    ready = current_trades is not None and current_trades >= int(min_trades)

    pass_primary = False
    if ready and current_dd is not None and leader_dd is not None:
        threshold = leader_dd - float(primary_epsilon or 0.0)
        pass_primary = current_dd >= threshold

    pass_secondary = False
    if ready and current_p50 is not None and current_avg is not None:
        pass_secondary = (current_p50 >= secondary_floor) and (
            current_avg >= secondary_floor
        )

    return WindowEval(
        window_name=window_name,
        ready=ready,
        current_trades=current_trades,
        leader_version=leader_version,
        leader_dd=leader_dd,
        current_dd=current_dd,
        current_p50=current_p50,
        current_avg=current_avg,
        pass_primary=pass_primary,
        pass_secondary=pass_secondary,
    )


def _format_eval(ev: WindowEval) -> str:
    return (
        f"{ev.window_name}: ready={ev.ready} "
        f"trades={ev.current_trades if ev.current_trades is not None else 'n/a'} "
        f"dd={ev.current_dd if ev.current_dd is not None else 'n/a'} "
        f"leader_dd={ev.leader_dd if ev.leader_dd is not None else 'n/a'} "
        f"p50={ev.current_p50 if ev.current_p50 is not None else 'n/a'} "
        f"avg={ev.current_avg if ev.current_avg is not None else 'n/a'} "
        f"pass_primary={ev.pass_primary} pass_secondary={ev.pass_secondary}"
    )


def _dd_gap(current_dd: Optional[float], leader_dd: Optional[float]) -> Optional[float]:
    if current_dd is None or leader_dd is None:
        return None
    return leader_dd - current_dd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--repo-root", default="/home/ander/CascadeProjects/cryptoalpha_lite"
    )
    parser.add_argument("--snapshots", default=None)

    parser.add_argument("--since", default="2026-02-23T17:39:10.184750Z")
    parser.add_argument("--hours", type=float, default=12.0)
    parser.add_argument("--min-trades", type=int, default=72)
    parser.add_argument("--secondary-floor", type=float, default=0.0)
    parser.add_argument("--interval", type=float, default=600.0)
    parser.add_argument("--confirm-streak", type=int, default=2)
    parser.add_argument("--cooldown-sec", type=float, default=3600.0)
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=8.0,
        help="Keep evaluating recently seen policy versions for this many hours after they stop being current",
    )

    parser.add_argument(
        "--baseline-version-a",
        default=None,
        help="Comparator policy_version for primary in window A (if omitted, stored in state on first run)",
    )

    parser.add_argument(
        "--primary-epsilon-a",
        type=float,
        default=0.0,
        help="Allowed drawdown degradation vs baseline in window A primary check (current_dd >= baseline_dd - epsilon)",
    )

    parser.add_argument("--heartbeat-sec", type=float, default=3600.0)
    parser.add_argument("--not-recommended-gap", type=float, default=0.005)

    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    snapshots_path = (
        Path(args.snapshots) if args.snapshots else _default_snapshots_path(repo_root)
    )
    state_path = repo_root / "backend" / ".promotion_recommender_state.json"

    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8", errors="replace"))
            if not isinstance(state, dict):
                state = {}
        except Exception:
            state = {}

    last_policy = state.get("policy_version")
    last_eval_policy = state.get("eval_policy_version")
    streak = int(state.get("streak") or 0)
    last_notify_ts = float(state.get("last_notify_ts") or 0.0)
    not_recommended_for = (
        state.get("not_recommended_for")
        if isinstance(state.get("not_recommended_for"), str)
        else None
    )
    not_recommended_brief_for = (
        state.get("not_recommended_brief_for")
        if isinstance(state.get("not_recommended_brief_for"), str)
        else None
    )
    not_actionable_for = (
        state.get("not_actionable_for")
        if isinstance(state.get("not_actionable_for"), str)
        else None
    )
    last_status_sig = (
        state.get("last_status_sig")
        if isinstance(state.get("last_status_sig"), str)
        else ""
    )
    last_heartbeat_ts = float(state.get("last_heartbeat_ts") or 0.0)
    baseline_version_a = args.baseline_version_a
    observed_versions: dict[str, float] = {}
    saved_obs = state.get("observed_versions")
    if isinstance(saved_obs, dict):
        for k, v in saved_obs.items():
            if isinstance(k, str) and k.strip() and isinstance(v, (int, float)):
                observed_versions[k] = float(v)

    baseline_version_a: Optional[str] = None
    if isinstance(args.baseline_version_a, str) and args.baseline_version_a.strip():
        baseline_version_a = args.baseline_version_a.strip()
    else:
        saved = state.get("baseline_version_a")
        baseline_version_a = saved if isinstance(saved, str) and saved.strip() else None

    while True:
        try:
            status = _read_json(
                args.api_base.rstrip("/") + "/api/rl/status",
                timeout_seconds=float(args.timeout),
            )
            policy = status.get("policy")
            policy_version = (
                policy.get("version")
                if isinstance(policy, dict) and isinstance(policy.get("version"), str)
                else None
            )
            active_policy_version = (
                status.get("active_policy_version")
                if isinstance(status.get("active_policy_version"), str)
                else None
            )
            now = time.time()
            cutoff = now - float(args.grace_hours) * 3600.0
            observed_versions = {
                k: v for k, v in observed_versions.items() if v >= cutoff
            }
            if policy_version:
                observed_versions[policy_version] = now

            if policy_version and policy_version != last_policy:
                last_policy = policy_version
                _emit_event("new_policy_version", f"policy_version={policy_version}")
                _notify("RL: новая policy_version", policy_version)

            # If baseline_version_a is not configured, fix it once to the first observed policy_version.
            # This makes window A compare against a stable baseline instead of the historical best leader.
            if baseline_version_a is None and (
                args.baseline_version_a is None
                or not str(args.baseline_version_a).strip()
            ):
                baseline_version_a = policy_version

            lines_a = _run_trades_report(
                repo_root=repo_root,
                snapshots_path=snapshots_path,
                min_trades=int(args.min_trades),
                since=str(args.since) if args.since else None,
                hours=None,
            )
            lines_b = _run_trades_report(
                repo_root=repo_root,
                snapshots_path=snapshots_path,
                min_trades=int(args.min_trades),
                since=None,
                hours=float(args.hours),
            )

            # Choose evaluation candidate: the freshest version (by version timestamp) that is
            # ready in both windows A and B, among recently observed versions (grace).
            candidate_versions = list(observed_versions.keys())
            candidate_versions.sort(
                key=lambda v: (
                    _parse_version_ts(v) or datetime.min.replace(tzinfo=timezone.utc)
                ),
                reverse=True,
            )

            eval_policy_version: Optional[str] = None
            eval_a: Optional[WindowEval] = None
            eval_b: Optional[WindowEval] = None

            for ver in candidate_versions:
                ev_a_tmp = _eval_window(
                    window_name="A",
                    lines=lines_a,
                    current_policy_version=ver,
                    min_trades=int(args.min_trades),
                    secondary_floor=float(args.secondary_floor),
                    baseline_policy_version=baseline_version_a,
                    primary_epsilon=float(args.primary_epsilon_a),
                )
                ev_b_tmp = _eval_window(
                    window_name="B",
                    lines=lines_b,
                    current_policy_version=ver,
                    min_trades=int(args.min_trades),
                    secondary_floor=float(args.secondary_floor),
                )
                if ev_a_tmp.ready and ev_b_tmp.ready:
                    eval_policy_version = ver
                    eval_a = ev_a_tmp
                    eval_b = ev_b_tmp
                    break

            # If nothing is ready yet, evaluate the current policy_version just for status visibility.
            if eval_policy_version is None:
                eval_policy_version = policy_version
                eval_a = _eval_window(
                    window_name="A",
                    lines=lines_a,
                    current_policy_version=eval_policy_version,
                    min_trades=int(args.min_trades),
                    secondary_floor=float(args.secondary_floor),
                    baseline_policy_version=baseline_version_a,
                    primary_epsilon=float(args.primary_epsilon_a),
                )
                eval_b = _eval_window(
                    window_name="B",
                    lines=lines_b,
                    current_policy_version=eval_policy_version,
                    min_trades=int(args.min_trades),
                    secondary_floor=float(args.secondary_floor),
                )

            if eval_policy_version != last_eval_policy:
                last_eval_policy = eval_policy_version
                streak = 0
                not_recommended_for = None
                not_recommended_brief_for = None
                last_status_sig = None

            ev_a = eval_a
            ev_b = eval_b

            all_ready = ev_a.ready and ev_b.ready
            pass_all = (
                all_ready
                and ev_a.pass_primary
                and ev_b.pass_primary
                and ev_a.pass_secondary
                and ev_b.pass_secondary
            )

            if (
                all_ready
                and (not pass_all)
                and (eval_policy_version is not None)
                and (not_recommended_brief_for != eval_policy_version)
            ):
                not_recommended_brief_for = eval_policy_version
                body = (
                    f"policy_version={eval_policy_version}\n"
                    f"A: trades={ev_a.current_trades} dd={ev_a.current_dd} leader_dd={ev_a.leader_dd} "
                    f"pass_primary={ev_a.pass_primary} pass_secondary={ev_a.pass_secondary}\n"
                    f"B: trades={ev_b.current_trades} dd={ev_b.current_dd} leader_dd={ev_b.leader_dd} "
                    f"pass_primary={ev_b.pass_primary} pass_secondary={ev_b.pass_secondary}\n"
                    "Рекомендация: НЕ промоутить эту версию; ждать новую policy_version"
                )
                _emit_event("NOT_RECOMMENDED", body)

            gap_a = _dd_gap(ev_a.current_dd, ev_a.leader_dd)
            gap_b = _dd_gap(ev_b.current_dd, ev_b.leader_dd)

            clearly_worse_primary = (
                all_ready
                and (not ev_a.pass_primary)
                and (not ev_b.pass_primary)
                and (gap_a is not None)
                and (gap_b is not None)
                and (gap_a >= float(args.not_recommended_gap))
                and (gap_b >= float(args.not_recommended_gap))
            )

            if clearly_worse_primary and not_recommended_for != eval_policy_version:
                not_recommended_for = eval_policy_version
                body = (
                    f"policy_version={eval_policy_version}\n"
                    f"A: trades={ev_a.current_trades} dd={ev_a.current_dd} leader_dd={ev_a.leader_dd} gap={gap_a}\n"
                    f"B: trades={ev_b.current_trades} dd={ev_b.current_dd} leader_dd={ev_b.leader_dd} gap={gap_b}\n"
                    f"min_trades={int(args.min_trades)} gap_threshold={float(args.not_recommended_gap)}\n"
                    "Рекомендация: НЕ промоутить эту версию; ждать новую policy_version"
                )
                _emit_event("NOT_RECOMMENDED", body)
                _notify("NOT_RECOMMENDED", body)

            status_sig = (
                f"policy_current={policy_version}"
                f"|policy_eval={eval_policy_version}"
                f"|streak={streak}"
                f"|pass_all={pass_all}"
                f"|A_ready={ev_a.ready}"
                f"|B_ready={ev_b.ready}"
                f"|A_dd={ev_a.current_dd}"
                f"|B_dd={ev_b.current_dd}"
                f"|A_leader_dd={ev_a.leader_dd}"
                f"|B_leader_dd={ev_b.leader_dd}"
                f"|A_baseline={baseline_version_a}"
                f"|notrec={not_recommended_for}"
            )

            should_print = False
            if status_sig != last_status_sig:
                should_print = True
            elif float(args.heartbeat_sec) > 0 and (now - last_heartbeat_ts) >= float(
                args.heartbeat_sec
            ):
                should_print = True

            if should_print:
                print(
                    f"{_now_utc()}  recommender_status  policy_version={policy_version}  eval_policy_version={eval_policy_version}  "
                    f"streak={streak}  pass_all={pass_all}  {_format_eval(ev_a)}  {_format_eval(ev_b)}",
                    flush=True,
                )
                last_status_sig = status_sig
                last_heartbeat_ts = now

            if pass_all:
                streak += 1
            else:
                streak = 0

            now = time.time()
            if streak >= int(args.confirm_streak):
                promotable = _is_promotable(
                    args.api_base,
                    eval_policy_version,
                    timeout_seconds=float(args.timeout),
                )

                if not promotable:
                    if (
                        eval_policy_version
                        and eval_policy_version != not_actionable_for
                    ):
                        not_actionable_for = eval_policy_version
                        body = (
                            f"policy_version={eval_policy_version}\n"
                            f"A: trades={ev_a.current_trades} dd={ev_a.current_dd} leader_dd={ev_a.leader_dd} p50={ev_a.current_p50} avg={ev_a.current_avg}\n"
                            f"B: trades={ev_b.current_trades} dd={ev_b.current_dd} leader_dd={ev_b.leader_dd} p50={ev_b.current_p50} avg={ev_b.current_avg}\n"
                            f"streak={streak}/{int(args.confirm_streak)}\n"
                            "Рекомендация: PROMOTE не применим (версия не сохранена в хранилище)\n"
                            "Действие: ждать следующую policy_version после retrain"
                        )
                        _emit_event("PROMOTE_NOT_ACTIONABLE", body)
                        _notify("PROMOTE_NOT_ACTIONABLE", body)
                else:
                    if (now - last_notify_ts) >= float(args.cooldown_sec):
                        last_notify_ts = now
                        body = (
                            f"policy_version={eval_policy_version}\n"
                            f"A: trades={ev_a.current_trades} dd={ev_a.current_dd} leader_dd={ev_a.leader_dd} p50={ev_a.current_p50} avg={ev_a.current_avg}\n"
                            f"B: trades={ev_b.current_trades} dd={ev_b.current_dd} leader_dd={ev_b.leader_dd} p50={ev_b.current_p50} avg={ev_b.current_avg}\n"
                            f"streak={streak}/{int(args.confirm_streak)}\n"
                            "Рекомендация: PROMOTE (вручную)\n"
                            f"Команда: curl -s -X POST {args.api_base.rstrip('/')}/api/rl/policy/promote -H 'Content-Type: application/json' -d '{{\"version\":\"{eval_policy_version}\"}}'\n"
                            f"Проверка: curl -s {args.api_base.rstrip('/')}/api/rl/status | grep -n 'active_policy' -A6"
                        )
                        if eval_policy_version != active_policy_version:
                            _emit_event("PROMOTE_RECOMMENDED", body)
                            _notify("PROMOTE_RECOMMENDED", body)

            state_path.write_text(
                json.dumps(
                    {
                        "policy_version": last_policy,
                        "eval_policy_version": last_eval_policy,
                        "streak": streak,
                        "last_notify_ts": last_notify_ts,
                        "not_recommended_for": not_recommended_for,
                        "not_recommended_brief_for": not_recommended_brief_for,
                        "not_actionable_for": not_actionable_for,
                        "last_status_sig": last_status_sig,
                        "last_heartbeat_ts": last_heartbeat_ts,
                        "baseline_version_a": baseline_version_a,
                        "observed_versions": observed_versions,
                        "updated_at": _now_utc(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"{_now_utc()}  recommender_error  error={exc}", flush=True)
            _notify("RL recommender: ошибка", str(exc))

        time.sleep(float(args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
