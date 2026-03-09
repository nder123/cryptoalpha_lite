from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable


@dataclass
class VersionAggregate:
    version: str
    start_collected_at: str | None = None
    end_collected_at: str | None = None
    snapshots: int = 0
    total_trades_first: int | None = None
    total_trades_last: int | None = None
    win_rate_last: float | None = None
    sharpe_last: float | None = None
    max_drawdown_last: float | None = None
    last_trade_pnl_pct_last: float | None = None
    last_trade_reward_last: float | None = None

    win_rate_sum: float = 0.0
    sharpe_sum: float = 0.0
    max_drawdown_sum: float = 0.0
    samples_for_avg: int = 0


@dataclass
class TradeAggregate:
    version: str
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    trades: int = 0
    wins: int = 0
    sum_pnl_pct: float = 0.0
    sumsq_pnl_pct: float = 0.0
    max_drawdown: float = 0.0
    equity: float = 0.0


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clip(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_latest_metrics(status: dict[str, Any]) -> dict[str, Any] | None:
    latest = status.get("latest_metrics")
    if isinstance(latest, dict):
        return latest
    return None


def _sort_key(ts: str | None) -> tuple[int, str]:
    if not ts:
        return (1, "")
    return (0, ts)


def _format_dt(raw: str | None) -> str:
    if not raw:
        return "n/a"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    return dt.isoformat(sep=" ", timespec="seconds")


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    ordered = sorted(values)
    k = int((pct / 100.0) * (len(ordered) - 1))
    if k < 0:
        k = 0
    if k >= len(ordered):
        k = len(ordered) - 1
    return ordered[k]


def _row_policy_version(row: dict[str, Any]) -> str | None:
    version = row.get("policy_version")
    if isinstance(version, str) and version:
        return version
    status = row.get("status")
    if not isinstance(status, dict):
        return None
    policy = status.get("policy")
    if not isinstance(policy, dict):
        return None
    version = policy.get("version")
    if isinstance(version, str) and version:
        return version
    return None


def _build_version_windows(rows: list[dict[str, Any]]) -> list[tuple[datetime, str]]:
    points: list[tuple[datetime, str]] = []
    last_version: str | None = None
    for row in rows:
        collected_at = _parse_dt(row.get("collected_at"))
        if collected_at is None:
            continue
        version = _row_policy_version(row)
        if not isinstance(version, str) or not version:
            continue
        if version != last_version:
            points.append((collected_at, version))
            last_version = version
    return points


def _version_at(windows: list[tuple[datetime, str]], ts: datetime) -> str | None:
    if not windows:
        return None
    lo = 0
    hi = len(windows) - 1
    best: str | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        start, version = windows[mid]
        if start <= ts:
            best = version
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _trade_id(trade: dict[str, Any]) -> str | None:
    # Prefer session_id if present; otherwise fall back to exit_directive_id.
    value = trade.get("session_id")
    if isinstance(value, str) and value:
        return value
    value = trade.get("exit_directive_id")
    if isinstance(value, str) and value:
        return value
    return None


def _iter_closed_trades(row: dict[str, Any]) -> Iterable[dict[str, Any]]:
    closed = row.get("closed_trades")
    if isinstance(closed, list):
        for item in closed:
            if isinstance(item, dict):
                yield item
        return
    closed = row.get("recent_closed")
    if isinstance(closed, list):
        for item in closed:
            if isinstance(item, dict):
                yield item
        return

    status = row.get("status")
    if not isinstance(status, dict):
        return

    closed = status.get("closed_trades")
    if isinstance(closed, list):
        for item in closed:
            if isinstance(item, dict):
                yield item
        return

    closed = status.get("recent_closed")
    if isinstance(closed, list):
        for item in closed:
            if isinstance(item, dict):
                yield item
        return


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Summarize rl_status snapshot JSONL grouped by policy.version"
    )
    parser.add_argument(
        "--mode",
        choices=("time", "trades"),
        default="time",
        help="Report mode: time-based snapshots summary or trade-based comparison",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include snapshots/trades at or after this ISO timestamp (e.g. 2026-02-23T11:00:00Z)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=None,
        help="Only include snapshots/trades from the last N hours (computed from latest collected_at)",
    )
    parser.add_argument(
        "--in",
        dest="input_path",
        default=str(
            Path(
                "~/CascadeProjects/cryptoalpha_lite/backend/rl_status_snapshots.jsonl"
            ).expanduser()
        ),
        help="Input JSONL file from rl_snapshots_collect.py",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        default=1,
        help="Minimum trades per version to include in output (trade mode)",
    )
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="Include trades that cannot be assigned to a known policy version",
    )
    parser.add_argument(
        "--clip-pnl-pct",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        help="Clip pnl_pct into [MIN, MAX] before aggregations (trade mode)",
    )
    parser.add_argument(
        "--sort",
        choices=(
            "first_seen",
            "trades",
            "win_rate",
            "avg_pnl_pct",
            "p50_pnl_pct",
            "p90_pnl_pct",
            "sum_pnl_pct",
            "sharpe_like",
            "max_drawdown",
        ),
        default="first_seen",
        help="Sort trade-mode output by a metric",
    )
    parser.add_argument(
        "--sort-order",
        choices=("asc", "desc"),
        default="desc",
        help="Sort order for --sort (trade mode). Note: max_drawdown is better when closer to 0 (higher).",
    )
    args = parser.parse_args(argv)

    path = Path(args.input_path).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    rows = list(_iter_jsonl(path))
    rows.sort(key=lambda r: _sort_key(r.get("collected_at")))

    since_dt: datetime | None = None
    if args.since is not None:
        since_dt = _parse_dt(args.since)
        if since_dt is None:
            raise SystemExit(f"Invalid --since timestamp: {args.since}")

    if args.hours is not None:
        try:
            hours = float(args.hours)
        except (TypeError, ValueError):
            raise SystemExit(f"Invalid --hours value: {args.hours}")
        if hours <= 0:
            raise SystemExit("--hours must be positive")
        latest_collected: datetime | None = None
        for row in reversed(rows):
            latest_collected = _parse_dt(row.get("collected_at"))
            if latest_collected is not None:
                break
        if latest_collected is not None:
            cutoff = latest_collected.timestamp() - (hours * 3600.0)
            since_from_hours = datetime.fromtimestamp(
                cutoff, tz=latest_collected.tzinfo
            )
            since_dt = (
                since_from_hours
                if since_dt is None
                else max(since_dt, since_from_hours)
            )

    if args.mode == "trades":
        aggregates: dict[str, TradeAggregate] = {}
        seen_trade_ids: set[str] = set()
        windows = _build_version_windows(rows)
        trade_pnls: dict[str, list[float]] = {}

        clip_lo: float | None = None
        clip_hi: float | None = None
        if args.clip_pnl_pct is not None:
            clip_lo = float(args.clip_pnl_pct[0])
            clip_hi = float(args.clip_pnl_pct[1])
            if clip_hi < clip_lo:
                clip_lo, clip_hi = clip_hi, clip_lo

        for row in rows:
            collected_at_raw = row.get("collected_at")
            collected_at = (
                collected_at_raw if isinstance(collected_at_raw, str) else None
            )
            collected_dt = _parse_dt(collected_at)

            if since_dt is not None and collected_dt is None:
                continue

            if since_dt is not None and collected_dt < since_dt:
                continue

            for trade in _iter_closed_trades(row):
                tid = _trade_id(trade)
                if not tid or tid in seen_trade_ids:
                    continue
                seen_trade_ids.add(tid)

                closed_dt = _parse_dt(trade.get("closed_at"))
                effective_dt = closed_dt or collected_dt
                if (
                    since_dt is not None
                    and effective_dt is not None
                    and effective_dt < since_dt
                ):
                    continue

                pnl_pct = _safe_float(trade.get("pnl_pct"))
                if pnl_pct is None:
                    continue

                if clip_lo is not None and clip_hi is not None:
                    pnl_pct = _clip(pnl_pct, clip_lo, clip_hi)

                assigned = (
                    _version_at(windows, closed_dt) if closed_dt is not None else None
                )
                if assigned is None:
                    fallback = _row_policy_version(row)
                    assigned = (
                        fallback
                        if isinstance(fallback, str) and fallback
                        else "unknown"
                    )

                if assigned == "unknown" and not args.include_unknown:
                    continue

                agg = aggregates.get(assigned)
                if agg is None:
                    agg = TradeAggregate(version=assigned)
                    aggregates[assigned] = agg

                if agg.first_seen_at is None:
                    agg.first_seen_at = collected_at
                agg.last_seen_at = collected_at

                agg.trades += 1
                if pnl_pct > 0:
                    agg.wins += 1
                agg.sum_pnl_pct += pnl_pct
                agg.sumsq_pnl_pct += pnl_pct * pnl_pct

                items = trade_pnls.get(assigned)
                if items is None:
                    items = []
                    trade_pnls[assigned] = items
                items.append(pnl_pct)

                agg.equity += pnl_pct
                if not hasattr(agg, "_equity_peak"):
                    setattr(agg, "_equity_peak", agg.equity)
                equity_peak = getattr(agg, "_equity_peak")
                if agg.equity > equity_peak:
                    equity_peak = agg.equity
                    setattr(agg, "_equity_peak", equity_peak)
                drawdown = agg.equity - equity_peak
                if drawdown < agg.max_drawdown:
                    agg.max_drawdown = drawdown

        rows_out: list[dict[str, Any]] = []
        min_trades = max(1, int(args.min_trades))

        for agg in aggregates.values():
            if agg.trades < min_trades:
                continue

            win_rate = (agg.wins / agg.trades) if agg.trades else None
            avg_pnl = (agg.sum_pnl_pct / agg.trades) if agg.trades else None

            pnls = trade_pnls.get(agg.version, [])
            p50 = median(pnls) if pnls else None
            p90 = _percentile(pnls, 90) if pnls else None
            min_pnl = min(pnls) if pnls else None
            max_pnl = max(pnls) if pnls else None

            sharpe_like = None
            if agg.trades and agg.trades > 1:
                mean = agg.sum_pnl_pct / agg.trades
                var = (agg.sumsq_pnl_pct - agg.trades * mean * mean) / (agg.trades - 1)
                std = var**0.5 if var > 0 else 0.0
                if std > 1e-9:
                    sharpe_like = mean / std

            rows_out.append(
                {
                    "version": agg.version,
                    "first_seen_at": agg.first_seen_at,
                    "last_seen_at": agg.last_seen_at,
                    "trades": agg.trades,
                    "win_rate": win_rate,
                    "avg_pnl_pct": avg_pnl,
                    "p50_pnl_pct": p50,
                    "p90_pnl_pct": p90,
                    "min_pnl_pct": min_pnl,
                    "max_pnl_pct": max_pnl,
                    "sum_pnl_pct": agg.sum_pnl_pct,
                    "sharpe_like": sharpe_like,
                    "max_drawdown": agg.max_drawdown,
                }
            )

        def _sort_value(row_out: dict[str, Any]) -> Any:
            key = args.sort
            if key == "first_seen":
                return _sort_key(row_out.get("first_seen_at"))
            return row_out.get(key)

        reverse = args.sort_order == "desc"

        def _key(row_out: dict[str, Any]) -> tuple[int, Any, tuple[int, str]]:
            v = _sort_value(row_out)
            missing = 1 if v is None else 0
            # Secondary sort keeps output stable.
            fallback = _sort_key(row_out.get("first_seen_at"))
            return (missing, v, fallback)

        rows_out.sort(key=_key, reverse=reverse)

        header = (
            f"{'version':<32}  {'first_seen':<19}  {'last_seen':<19}  {'trades':>6}  {'win_rate':>8}  "
            f"{'avg_pnl_pct':>11}  {'p50_pnl_pct':>11}  {'p90_pnl_pct':>11}  {'min_pnl_pct':>11}  "
            f"{'max_pnl_pct':>11}  {'sum_pnl_pct':>11}  {'sharpe_like':>11}  {'max_drawdown':>12}"
        )
        print(header)
        for row_out in rows_out:
            first_seen = _format_dt(row_out.get("first_seen_at"))
            last_seen = _format_dt(row_out.get("last_seen_at"))
            trades = int(row_out["trades"])
            win_rate = row_out.get("win_rate")
            avg_pnl_pct = row_out.get("avg_pnl_pct")
            p50_pnl_pct = row_out.get("p50_pnl_pct")
            p90_pnl_pct = row_out.get("p90_pnl_pct")
            min_pnl_pct = row_out.get("min_pnl_pct")
            max_pnl_pct = row_out.get("max_pnl_pct")
            sum_pnl_pct = row_out.get("sum_pnl_pct")
            sharpe_like = row_out.get("sharpe_like")
            max_drawdown = row_out.get("max_drawdown")

            line = (
                f"{row_out['version']:<32}  {first_seen:<19}  {last_seen:<19}  {trades:>6d}  "
                f"{(f'{win_rate:.4f}' if win_rate is not None else 'n/a'):>8}  "
                f"{(f'{avg_pnl_pct:.4f}' if avg_pnl_pct is not None else 'n/a'):>11}  "
                f"{(f'{p50_pnl_pct:.4f}' if p50_pnl_pct is not None else 'n/a'):>11}  "
                f"{(f'{p90_pnl_pct:.4f}' if p90_pnl_pct is not None else 'n/a'):>11}  "
                f"{(f'{min_pnl_pct:.4f}' if min_pnl_pct is not None else 'n/a'):>11}  "
                f"{(f'{max_pnl_pct:.4f}' if max_pnl_pct is not None else 'n/a'):>11}  "
                f"{(f'{sum_pnl_pct:.4f}' if sum_pnl_pct is not None else 'n/a'):>11}  "
                f"{(f'{sharpe_like:.4f}' if sharpe_like is not None else 'n/a'):>11}  "
                f"{(f'{max_drawdown:.4f}' if max_drawdown is not None else 'n/a'):>12}"
            )
            print(line)
        return

    aggregates: dict[str, VersionAggregate] = {}

    for row in rows:
        status = row.get("status")
        if not isinstance(status, dict):
            continue
        version = _row_policy_version(row)
        if not isinstance(version, str) or not version:
            version = "unknown"

        agg = aggregates.get(version)
        if agg is None:
            agg = VersionAggregate(version=version)
            aggregates[version] = agg

        collected_at = row.get("collected_at")
        if isinstance(collected_at, str):
            if agg.start_collected_at is None:
                agg.start_collected_at = collected_at
            agg.end_collected_at = collected_at

        agg.snapshots += 1

        latest = _get_latest_metrics(status)
        if latest is None:
            continue

        total_trades = _safe_int(latest.get("total_trades"))
        if agg.total_trades_first is None and total_trades is not None:
            agg.total_trades_first = total_trades
        if total_trades is not None:
            agg.total_trades_last = total_trades

        win_rate = _safe_float(latest.get("win_rate"))
        sharpe = _safe_float(latest.get("sharpe_ratio"))
        max_dd = _safe_float(latest.get("max_drawdown"))
        last_pnl = _safe_float(latest.get("last_trade_pnl_pct"))
        last_reward = _safe_float(latest.get("last_trade_reward"))

        agg.win_rate_last = win_rate
        agg.sharpe_last = sharpe
        agg.max_drawdown_last = max_dd
        agg.last_trade_pnl_pct_last = last_pnl
        agg.last_trade_reward_last = last_reward

        if win_rate is not None and sharpe is not None and max_dd is not None:
            agg.win_rate_sum += win_rate
            agg.sharpe_sum += sharpe
            agg.max_drawdown_sum += max_dd
            agg.samples_for_avg += 1

    # Print summary table
    ordered = sorted(aggregates.values(), key=lambda a: _sort_key(a.start_collected_at))

    header = (
        f"{'version':<32}  {'window_start':<19}  {'window_end':<19}  {'snapshots':>9}  {'trades_delta':>11}  "
        f"{'win_rate_last':>12}  {'sharpe_last':>10}  {'max_dd_last':>10}  {'win_rate_avg':>12}  {'sharpe_avg':>10}  {'max_dd_avg':>10}"
    )
    print(header)

    for agg in ordered:
        trades_delta = None
        if agg.total_trades_first is not None and agg.total_trades_last is not None:
            trades_delta = agg.total_trades_last - agg.total_trades_first

        win_avg = (
            (agg.win_rate_sum / agg.samples_for_avg) if agg.samples_for_avg else None
        )
        sharpe_avg = (
            (agg.sharpe_sum / agg.samples_for_avg) if agg.samples_for_avg else None
        )
        dd_avg = (
            (agg.max_drawdown_sum / agg.samples_for_avg)
            if agg.samples_for_avg
            else None
        )

        cols = [
            agg.version,
            _format_dt(agg.start_collected_at),
            _format_dt(agg.end_collected_at),
            str(agg.snapshots),
            str(trades_delta) if trades_delta is not None else "n/a",
            f"{agg.win_rate_last:.4f}" if agg.win_rate_last is not None else "n/a",
            f"{agg.sharpe_last:.4f}" if agg.sharpe_last is not None else "n/a",
            (
                f"{agg.max_drawdown_last:.4f}"
                if agg.max_drawdown_last is not None
                else "n/a"
            ),
            f"{win_avg:.4f}" if win_avg is not None else "n/a",
            f"{sharpe_avg:.4f}" if sharpe_avg is not None else "n/a",
            f"{dd_avg:.4f}" if dd_avg is not None else "n/a",
        ]

        version, window_start, window_end = cols[0], cols[1], cols[2]
        snapshots = int(cols[3])
        trades_delta_s = cols[4]
        win_last_s, sharpe_last_s, dd_last_s = cols[5], cols[6], cols[7]
        win_avg_s, sharpe_avg_s, dd_avg_s = cols[8], cols[9], cols[10]
        print(
            f"{version:<32}  {window_start:<19}  {window_end:<19}  {snapshots:>9d}  {trades_delta_s:>11}  "
            f"{win_last_s:>12}  {sharpe_last_s:>10}  {dd_last_s:>10}  {win_avg_s:>12}  {sharpe_avg_s:>10}  {dd_avg_s:>10}"
        )


if __name__ == "__main__":
    main()
