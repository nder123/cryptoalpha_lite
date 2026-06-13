from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.evaluation_runner import _generate_signals
from scripts.behavior_validation.execution_simulator import simulate_execution
from scripts.behavior_validation.metrics_v1 import build_metrics_v1

DEFAULT_THRESHOLD = 0.001


def run_decision_isolation(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    signals = _signals_with_magnitude(data)
    report = {
        "force_pass": run_force_pass_test(signals),
        "threshold_relaxation": run_threshold_relaxation_test(
            signals,
            threshold=threshold,
        ),
        "signal_echo": run_signal_echo_test(signals),
    }
    report["case"] = _classify_case(report)
    _write_report(output_dir or _default_output_dir(), report)
    return report


def run_force_pass_test(
    signals: Sequence[dict[str, object]],
) -> dict[str, object]:
    decisions = tuple(
        _decision(index=index, signal=signal, value=1.0)
        for index, signal in enumerate(signals, start=1)
        if signal is not None
    )
    metrics = _metrics(signals=signals, decisions=decisions)
    return {
        "decision_flow": _flow(metrics),
        "decisions_generated": metrics["decisions_generated"],
        "executions_attempted": metrics["executions_attempted"],
        "metrics_v1": metrics,
    }


def run_threshold_relaxation_test(
    signals: Sequence[dict[str, object]],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, object]:
    decisions = tuple(
        _decision(
            index=index,
            signal=signal,
            value=_signal_magnitude(signal),
        )
        for index, signal in enumerate(signals, start=1)
        if _signal_magnitude(signal) >= threshold
    )
    metrics = _metrics(signals=signals, decisions=decisions)
    return {
        "threshold": threshold,
        "decision_flow": _flow(metrics),
        "decisions_generated": metrics["decisions_generated"],
        "executions_attempted": metrics["executions_attempted"],
        "metrics_v1": metrics,
    }


def run_signal_echo_test(
    signals: Sequence[dict[str, object]],
) -> dict[str, object]:
    decisions = tuple(
        _decision(
            index=index,
            signal=signal,
            value=_signal_magnitude(signal),
        )
        for index, signal in enumerate(signals, start=1)
    )
    metrics = _metrics(signals=signals, decisions=decisions)
    return {
        "decision_flow": _flow(metrics),
        "decisions_generated": metrics["decisions_generated"],
        "executions_attempted": metrics["executions_attempted"],
        "signal_decision_correlation": _same_value_ratio(
            tuple(_signal_magnitude(signal) for signal in signals),
            tuple(_decision_value(decision) for decision in decisions),
        ),
        "metrics_v1": metrics,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run decision isolation checks")
    parser.add_argument("historical_data", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_decision_isolation(
        args.historical_data,
        output_dir=args.output_dir,
        threshold=args.threshold,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _signals_with_magnitude(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    base_signals = _generate_signals(data)
    return tuple(
        {
            **signal,
            "signal_magnitude": _candle_magnitude(row),
            "signal_direction": _candle_direction(row),
        }
        for signal, row in zip(base_signals, data, strict=True)
    )


def _decision(
    *,
    index: int,
    signal: dict[str, object],
    value: float,
) -> dict[str, object]:
    return {
        "decision_id": f"isolation-decision-{index}",
        "source_signal_id": signal["signal_id"],
        "symbol": signal.get("symbol"),
        "timestamp": signal.get("timestamp"),
        "decision_value": value,
        "simulation_status": signal["simulation_status"],
    }


def _metrics(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
) -> dict[str, object]:
    executions = tuple(simulate_execution(decision) for decision in decisions)
    return build_metrics_v1(
        signals=signals,
        decisions=decisions,
        executions=executions,
    )


def _flow(metrics: dict[str, object]) -> str:
    if _int_value(metrics.get("decisions_generated")) > 0:
        return "alive"
    return "dead"


def _classify_case(report: dict[str, object]) -> str:
    force_pass = _nested_int(report, "force_pass", "executions_attempted")
    echo_correlation = _nested_float(
        report,
        "signal_echo",
        "signal_decision_correlation",
    )
    if force_pass > 0 and echo_correlation > 0.0:
        return "CASE_A_DECISION_LAYER_BLOCKS_SIGNAL_INFORMATION"
    return "CASE_B_SIGNAL_OR_DATA_LAYER_DEAD"


def _candle_magnitude(row: dict[str, object]) -> float:
    open_price = _float_value(row.get("open"))
    close_price = _float_value(row.get("close"))
    if open_price == 0.0:
        return 0.0
    return abs(close_price - open_price) / open_price


def _candle_direction(row: dict[str, object]) -> float:
    open_price = _float_value(row.get("open"))
    close_price = _float_value(row.get("close"))
    if close_price >= open_price:
        return 1.0
    return -1.0


def _signal_magnitude(signal: dict[str, object]) -> float:
    return _float_value(signal.get("signal_magnitude"))


def _decision_value(decision: dict[str, object]) -> float:
    return _float_value(decision.get("decision_value"))


def _same_value_ratio(left: Sequence[float], right: Sequence[float]) -> float:
    denominator = max(len(left), len(right))
    if denominator == 0:
        return 0.0

    same = sum(
        1
        for left_value, right_value in zip(left, right, strict=False)
        if left_value == right_value
    )
    return same / denominator


def _nested_int(
    payload: dict[str, object],
    section: str,
    key: str,
) -> int:
    section_payload = payload.get(section)
    if not isinstance(section_payload, dict):
        return 0
    return _int_value(section_payload.get(key))


def _nested_float(
    payload: dict[str, object],
    section: str,
    key: str,
) -> float:
    section_payload = payload.get(section)
    if not isinstance(section_payload, dict):
        return 0.0
    return _float_value(section_payload.get(key))


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "decision_isolation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
