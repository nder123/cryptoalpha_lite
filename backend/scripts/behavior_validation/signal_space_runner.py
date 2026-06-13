from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.edge_validation_runner import _generate_edge_signals
from scripts.behavior_validation.feature_transform import generate_signal_v2


def run_signal_space_comparison(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    signal_v1 = _generate_edge_signals(data)
    signal_v2 = generate_signal_v2(data)
    report = {
        "signal_v1": _signal_metrics(
            signal_v1,
            label_key="signal_v1_bucket",
            direction_key="signal_v1_direction",
        ),
        "signal_v2": _signal_metrics(
            signal_v2,
            label_key="signal_v2_bucket",
            direction_key="signal_v2_direction",
        ),
        "features": [
            "volatility_regime",
            "market_structure",
            "delta_acceleration",
            "volatility_cluster",
            "range_behavior",
            "range_expansion",
            "normalized_deviation",
            "z_score",
            "relative_strength",
        ],
    }
    report["delta"] = {
        "mutual_information_proxy_delta": _float_value(
            report["signal_v2"]["mutual_information_proxy"]
        )
        - _float_value(report["signal_v1"]["mutual_information_proxy"]),
        "directional_alignment_delta": _float_value(
            report["signal_v2"]["directional_alignment"]
        )
        - _float_value(report["signal_v1"]["directional_alignment"]),
    }
    report["winner"] = _winner(report)
    _write_report(output_dir or _default_output_dir(), report)
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run signal space v1/v2 comparison")
    parser.add_argument("historical_data", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_signal_space_comparison(
        args.historical_data,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _signal_metrics(
    signals: Sequence[dict[str, object]],
    *,
    label_key: str,
    direction_key: str,
) -> dict[str, object]:
    prepared = tuple(
        _prepare_signal(signal, label_key=label_key, direction_key=direction_key)
        for signal in signals
        if signal.get("outcome_direction") is not None
    )
    labels = tuple(label for label, _, _ in prepared)
    directions = tuple(direction for _, direction, _ in prepared)
    outcomes = tuple(outcome for _, _, outcome in prepared)
    return {
        "samples": len(prepared),
        "mutual_information_proxy": _normalized_mutual_information(labels, outcomes),
        "directional_alignment": _directional_alignment(directions, outcomes),
        "unique_signal_states": len(set(labels)),
    }


def _prepare_signal(
    signal: dict[str, object],
    *,
    label_key: str,
    direction_key: str,
) -> tuple[str, str, str]:
    outcome = str(signal["outcome_direction"])
    if label_key == "signal_v1_bucket":
        label = _signal_v1_bucket(signal)
    else:
        label = str(signal[label_key])

    if direction_key == "signal_v1_direction":
        direction = _signal_v1_direction(signal)
    else:
        direction = str(signal[direction_key])
    return label, direction, outcome


def _signal_v1_bucket(signal: dict[str, object]) -> str:
    return _signal_v1_direction(signal)


def _signal_v1_direction(signal: dict[str, object]) -> str:
    if _float_value(signal.get("close")) >= _float_value(signal.get("open")):
        return "long"
    return "short"


def _normalized_mutual_information(
    labels: Sequence[str],
    outcomes: Sequence[str],
) -> float:
    if not labels or not outcomes:
        return 0.0

    outcome_entropy = _entropy(outcomes)
    if outcome_entropy == 0.0:
        return 0.0

    joint_counts = Counter(zip(labels, outcomes, strict=True))
    label_counts = Counter(labels)
    outcome_counts = Counter(outcomes)
    total = len(labels)
    mutual_information = 0.0
    for (label, outcome), joint_count in joint_counts.items():
        joint_probability = joint_count / total
        label_probability = label_counts[label] / total
        outcome_probability = outcome_counts[outcome] / total
        mutual_information += joint_probability * math.log2(
            joint_probability / (label_probability * outcome_probability)
        )
    return mutual_information / outcome_entropy


def _entropy(values: Sequence[str]) -> float:
    total = len(values)
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in Counter(values).values():
        probability = count / total
        entropy -= probability * math.log2(probability)
    return entropy


def _directional_alignment(
    directions: Sequence[str],
    outcomes: Sequence[str],
) -> float:
    if not directions or not outcomes:
        return 0.0
    matches = sum(
        1
        for direction, outcome in zip(directions, outcomes, strict=True)
        if direction == outcome
    )
    return matches / len(directions)


def _winner(report: dict[str, object]) -> str:
    delta = report.get("delta", {})
    if not isinstance(delta, dict):
        return "none"
    value = _float_value(delta.get("mutual_information_proxy_delta"))
    if value > 0.0:
        return "signal_v2"
    if value < 0.0:
        return "signal_v1"
    return "none"


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "signal_space_v1.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
