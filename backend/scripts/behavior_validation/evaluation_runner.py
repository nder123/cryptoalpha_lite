from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.execution_simulator import simulate_execution
from scripts.behavior_validation.metrics import build_metrics
from scripts.behavior_validation.metrics_v1 import build_metrics_v1
from scripts.behavior_validation.report_schema import build_report

DEFAULT_DATA = (
    {
        "event_id": "sample-001",
        "simulation_status": "accepted",
    },
    {
        "event_id": "sample-002",
        "simulation_status": "rejected",
    },
    {
        "event_id": "sample-003",
        "simulation_status": "delayed",
    },
)

DEFAULT_RUN_ID = "behavior-evaluation-v1"


def run_evaluation(
    *,
    data: Sequence[dict[str, object]] = DEFAULT_DATA,
    run_id: str = DEFAULT_RUN_ID,
    output_dir: Path | None = None,
    input_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    signals = _generate_signals(data)
    decisions = _generate_decisions(signals)
    executions = tuple(simulate_execution(decision) for decision in decisions)
    metrics = build_metrics(signals, decisions, executions)
    metrics_v1 = build_metrics_v1(
        signals=signals,
        decisions=decisions,
        executions=executions,
    )
    report = build_report(
        run_id=run_id,
        signals=len(signals),
        decisions=len(decisions),
        executions=len(executions),
        metrics=metrics,
        metrics_v1=metrics_v1,
    )

    _write_artifacts(
        output_dir or _default_output_dir(),
        report,
        metrics,
        metrics_v1,
        input_summary or _input_summary(data),
    )
    return report


def run_historical_evaluation(
    dataset_path: Path | str,
    *,
    run_id: str = DEFAULT_RUN_ID,
    output_dir: Path | None = None,
) -> dict[str, object]:
    raw_data = load_historical_data(dataset_path)
    data = normalize_dataset(raw_data)
    return run_evaluation(
        data=data,
        run_id=run_id,
        output_dir=output_dir,
        input_summary=_input_summary(data),
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run behavior evaluation harness")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    parser.add_argument(
        "--historical-data",
        type=Path,
        default=None,
        help="CSV file or directory of CSV files to use as historical input",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    if args.historical_data is None:
        report = run_evaluation(run_id=args.run_id, output_dir=args.output_dir)
    else:
        report = run_historical_evaluation(
            args.historical_data,
            run_id=args.run_id,
            output_dir=args.output_dir,
        )
    print(json.dumps(report, indent=2, sort_keys=True))


def _generate_signals(
    data: Sequence[dict[str, object]]
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "signal_id": f"signal-{index}",
            "source_event_id": row["event_id"],
            "symbol": row.get("symbol"),
            "timestamp": row.get("timestamp"),
            "signal_strength": _signal_strength(row),
            "signal_sensitivity": _signal_sensitivity(row),
            "signal_delta": _signal_delta(row),
            "signal_type": _signal_type(row),
            "simulation_status": row["simulation_status"],
        }
        for index, row in enumerate(data, start=1)
    )


def _generate_decisions(
    signals: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "decision_id": f"decision-{index}",
            "source_signal_id": signal["signal_id"],
            "symbol": signal.get("symbol"),
            "timestamp": signal.get("timestamp"),
            "decision_score": _decision_score(signal),
            "direction": _decision_direction(signal),
            "simulation_status": signal["simulation_status"],
        }
        for index, signal in enumerate(signals, start=1)
    )


def _decision_score(signal: dict[str, object]) -> float:
    return (
        0.5 * _signal_strength(signal)
        + 0.3 * _signal_sensitivity(signal)
        + 0.2 * _signal_delta(signal)
    )


def _decision_direction(signal: dict[str, object]) -> str:
    if _signal_delta(signal) >= 0.0:
        return "long"
    return "short"


def _signal_strength(payload: dict[str, object]) -> float:
    existing = payload.get("signal_strength")
    if isinstance(existing, int | float):
        return float(existing)

    open_price = _float_value(payload.get("open"))
    close_price = _float_value(payload.get("close"))
    if open_price == 0.0:
        return 0.0
    return abs(close_price - open_price) / open_price


def _signal_sensitivity(payload: dict[str, object]) -> float:
    existing = payload.get("signal_sensitivity")
    if isinstance(existing, int | float):
        return float(existing)

    high_price = _float_value(payload.get("high"))
    low_price = _float_value(payload.get("low"))
    open_price = _float_value(payload.get("open"))
    if open_price == 0.0:
        return 0.0
    return abs(high_price - low_price) / open_price


def _signal_delta(payload: dict[str, object]) -> float:
    existing = payload.get("signal_delta")
    if isinstance(existing, int | float):
        return float(existing)

    open_price = _float_value(payload.get("open"))
    close_price = _float_value(payload.get("close"))
    if open_price == 0.0:
        return 0.0
    return (close_price - open_price) / open_price


def _signal_type(payload: dict[str, object]) -> str:
    if _signal_delta(payload) >= 0.0:
        return "positive_delta"
    return "negative_delta"


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_artifacts(
    output_dir: Path,
    report: dict[str, object],
    metrics: dict[str, int],
    metrics_v1: dict[str, object],
    input_summary: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps({**metrics, "metrics_v1": metrics_v1}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "input_summary.json").write_text(
        json.dumps(input_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_optional_debug_insights(output_dir, metrics_v1)


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


def _write_optional_insights_diff(output_dir: Path) -> None:
    from scripts.behavior_validation.insights_diff_v1 import diff_insights_files

    if os.getenv("ENABLE_INSIGHTS_DIFF", "false").lower() != "true":
        return

    previous_path = os.getenv("PREVIOUS_INSIGHTS_PATH")
    if previous_path is None:
        return

    diff = diff_insights_files(previous_path, output_dir / "insights.json")
    (output_dir / "insights_diff.json").write_text(
        json.dumps(diff, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_optional_debug_insights(
    output_dir: Path,
    metrics_v1: dict[str, object],
) -> None:
    if os.getenv("ENABLE_BEHAVIOR_INSIGHTS_DEBUG", "false").lower() != "true":
        return

    from scripts.behavior_validation.insights_v1 import build_insights_v1

    insights_v1 = build_insights_v1(metrics_v1)
    (output_dir / "insights.json").write_text(
        json.dumps(insights_v1, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_optional_insights_diff(output_dir)


def _input_summary(data: Sequence[dict[str, object]]) -> dict[str, object]:
    symbols = sorted(
        {str(row["symbol"]) for row in data if row.get("symbol") is not None}
    )
    timestamps = sorted(
        str(row["timestamp"]) for row in data if row.get("timestamp") is not None
    )
    if timestamps:
        time_range = f"{timestamps[0]}..{timestamps[-1]}"
    else:
        time_range = "n/a"

    return {
        "rows": len(data),
        "symbols": symbols,
        "time_range": time_range,
    }


if __name__ == "__main__":
    main()
