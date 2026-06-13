from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.baseline_generators import (
    generate_naive_momentum,
    generate_random_decisions,
)
from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.edge_validation_runner import (
    MODES,
    _evaluate_mode,
    _generate_edge_signals,
)
from scripts.behavior_validation.evaluation_runner import _generate_decisions

DEFAULT_SEEDS = (1, 2, 3, 10, 42)
WINDOW_NAMES = ("early", "mid", "late")
STABILITY_VARIANCE_THRESHOLD = 0.0001


def run_statistical_edge_validation(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
    seeds: Sequence[int] = DEFAULT_SEEDS,
) -> dict[str, object]:
    data = _sorted_data(normalize_dataset(load_historical_data(dataset_path)))
    full_runs = tuple(_run_modes(data, seed=seed) for seed in seeds)
    window_runs = {
        window_name: tuple(_run_modes(window_data, seed=seed) for seed in seeds)
        for window_name, window_data in _windowed_data(data).items()
    }

    report = {mode: _aggregate_mode(mode=mode, runs=full_runs) for mode in MODES}
    report["stability"] = {
        mode: _stability_classification(report[mode]["variance"]) for mode in MODES
    }
    report["windows"] = {
        window_name: {mode: _aggregate_mode(mode=mode, runs=runs) for mode in MODES}
        for window_name, runs in window_runs.items()
    }
    report["case"] = _case_classification(report)
    _write_report(output_dir or _default_output_dir(), report)
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run statistical edge validation")
    parser.add_argument("historical_data", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_statistical_edge_validation(
        args.historical_data,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _run_modes(
    data: Sequence[dict[str, object]],
    *,
    seed: int,
) -> dict[str, dict[str, object]]:
    signals = _generate_edge_signals(data)
    return {
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


def _aggregate_mode(
    *,
    mode: str,
    runs: Sequence[dict[str, dict[str, object]]],
) -> dict[str, float]:
    hit_rates = tuple(_metric(run, mode, "hit_rate") for run in runs)
    decision_densities = tuple(
        _metrics_v1_metric(run, mode, "decision_density") for run in runs
    )
    execution_rates = tuple(_execution_rate(run[mode]["metrics_v1"]) for run in runs)
    return {
        "mean_hit_rate": _mean(hit_rates),
        "variance": _variance(hit_rates),
        "mean_decision_density": _mean(decision_densities),
        "mean_execution_rate": _mean(execution_rates),
    }


def _windowed_data(
    data: Sequence[dict[str, object]],
) -> dict[str, tuple[dict[str, object], ...]]:
    timestamps = tuple(sorted({str(row["timestamp"]) for row in data}))
    timestamp_windows = _split_sequence(timestamps, len(WINDOW_NAMES))
    return {
        window_name: tuple(
            row for row in data if str(row["timestamp"]) in set(window_timestamps)
        )
        for window_name, window_timestamps in zip(
            WINDOW_NAMES,
            timestamp_windows,
            strict=True,
        )
    }


def _split_sequence(
    values: Sequence[str],
    parts: int,
) -> tuple[tuple[str, ...], ...]:
    base_size = len(values) // parts
    remainder = len(values) % parts
    windows = []
    start = 0
    for index in range(parts):
        size = base_size + (1 if index < remainder else 0)
        windows.append(tuple(values[start : start + size]))
        start += size
    return tuple(windows)


def _case_classification(report: dict[str, object]) -> str:
    system = _mode_aggregate(report, "system")
    random = _mode_aggregate(report, "random")
    naive = _mode_aggregate(report, "naive")
    system_stable = _stability_classification(system["variance"]) == "stable"

    if system["mean_hit_rate"] < random["mean_hit_rate"] and system_stable:
        return "CASE_A_SYSTEM_BELOW_RANDOM_STABLE"
    if system["mean_hit_rate"] > naive["mean_hit_rate"] and system_stable:
        return "CASE_C_SYSTEM_ABOVE_NAIVE_STABLE"
    return "CASE_B_SYSTEM_RANDOM_UNSTABLE"


def _mode_aggregate(
    report: dict[str, object],
    mode: str,
) -> dict[str, float]:
    aggregate = report.get(mode, {})
    if isinstance(aggregate, dict):
        return {
            "mean_hit_rate": _float_value(aggregate.get("mean_hit_rate")),
            "variance": _float_value(aggregate.get("variance")),
        }
    return {"mean_hit_rate": 0.0, "variance": 0.0}


def _stability_classification(variance: object) -> str:
    if _float_value(variance) <= STABILITY_VARIANCE_THRESHOLD:
        return "stable"
    return "unstable"


def _metric(
    run: dict[str, dict[str, object]],
    mode: str,
    key: str,
) -> float:
    return _float_value(run[mode].get(key))


def _metrics_v1_metric(
    run: dict[str, dict[str, object]],
    mode: str,
    key: str,
) -> float:
    metrics_v1 = run[mode].get("metrics_v1", {})
    if not isinstance(metrics_v1, dict):
        return 0.0
    return _float_value(metrics_v1.get(key))


def _execution_rate(metrics_v1: object) -> float:
    if not isinstance(metrics_v1, dict):
        return 0.0
    signals_generated = _float_value(metrics_v1.get("signals_generated"))
    executions_attempted = _float_value(metrics_v1.get("executions_attempted"))
    if signals_generated == 0.0:
        return 0.0
    return executions_attempted / signals_generated


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _sorted_data(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(
        sorted(
            data,
            key=lambda row: (str(row["timestamp"]), str(row["symbol"])),
        )
    )


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "statistical_edge_v1.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
