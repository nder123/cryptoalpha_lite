from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.baseline_generators import (
    generate_naive_momentum,
    generate_random_decisions,
)
from scripts.behavior_validation.comparison_metrics import build_comparison_metrics
from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.evaluation_runner import _generate_decisions
from scripts.behavior_validation.execution_simulator import simulate_execution
from scripts.behavior_validation.metrics_v1 import build_metrics_v1

MODES = ("random", "naive", "system")


def run_edge_validation(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
    seed: int = 0,
) -> dict[str, object]:
    raw_data = load_historical_data(dataset_path)
    data = normalize_dataset(raw_data)
    signals = _generate_edge_signals(data)
    mode_results = {
        "random": _evaluate_mode(
            signals=signals,
            decisions=generate_random_decisions(signals, seed=seed),
        ),
        "naive": _evaluate_mode(
            signals=signals,
            decisions=generate_naive_momentum(signals),
        ),
        "system": _evaluate_mode(
            signals=signals,
            decisions=_generate_decisions(signals),
        ),
    }
    report = {**mode_results, "winner": _winner(mode_results)}
    _write_edge_report(output_dir or _default_output_dir(), report)
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run edge validation comparison")
    parser.add_argument("historical_data", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_edge_validation(
        args.historical_data,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _evaluate_mode(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
) -> dict[str, object]:
    executions = tuple(simulate_execution(decision) for decision in decisions)
    metrics_v1 = build_metrics_v1(
        signals=signals,
        decisions=decisions,
        executions=executions,
    )
    comparison = build_comparison_metrics(
        signals=signals,
        decisions=decisions,
        executions=executions,
        metrics_v1=metrics_v1,
    )
    return {
        **comparison,
        "metrics_v1": metrics_v1,
    }


def _generate_edge_signals(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    outcome_by_event_id = _outcomes_by_event_id(data)
    return tuple(
        {
            "signal_id": f"signal-{index}",
            "source_event_id": row["event_id"],
            "symbol": row.get("symbol"),
            "timestamp": row.get("timestamp"),
            "open": row.get("open"),
            "close": row.get("close"),
            "outcome_direction": outcome_by_event_id.get(str(row["event_id"])),
            "simulation_status": row["simulation_status"],
        }
        for index, row in enumerate(data, start=1)
    )


def _outcomes_by_event_id(
    data: Sequence[dict[str, object]],
) -> dict[str, str]:
    rows_by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in data:
        rows_by_symbol[str(row["symbol"])].append(row)

    outcomes: dict[str, str] = {}
    for rows in rows_by_symbol.values():
        sorted_rows = sorted(rows, key=lambda row: str(row["timestamp"]))
        for current, next_row in zip(sorted_rows, sorted_rows[1:], strict=False):
            outcomes[str(current["event_id"])] = _price_direction(
                current.get("close"),
                next_row.get("close"),
            )
    return outcomes


def _price_direction(current_close: object, next_close: object) -> str:
    if _float_value(next_close) >= _float_value(current_close):
        return "long"
    return "short"


def _winner(results: dict[str, dict[str, object]]) -> str:
    scores = {mode: _score(result) for mode, result in results.items() if mode in MODES}
    best_score = max(scores.values(), default=0.0)
    if best_score <= 0.0:
        return "none"

    winners = tuple(mode for mode, score in scores.items() if score == best_score)
    if len(winners) != 1:
        return "none"
    return winners[0]


def _score(result: dict[str, object]) -> float:
    return _float_value(result.get("hit_rate"))


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_edge_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "edge_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
