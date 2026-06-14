from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.economic_closure_runner import (
    _build_report,
    _future_returns_by_event_id,
    _reward,
)
from scripts.behavior_validation.edge_validation_runner import _outcomes_by_event_id
from scripts.behavior_validation.evaluation_runner import _generate_decisions
from scripts.behavior_validation.execution_simulator import simulate_execution
from scripts.behavior_validation.feature_transform import (
    generate_signal_v2,
    transform_market_features,
)
from scripts.behavior_validation.feature_transform_microstructure_v2 import (
    enrich_dataset_with_microstructure_features,
    transform_microstructure_features_v2,
)
from scripts.behavior_validation.metrics_v1 import build_metrics_v1

SUMMARY_FILENAME = "feature_impact_analysis_v1.json"
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
IDENTITY_KEYS = {"event_id", "symbol", "timestamp"}


def run_feature_impact_analysis(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    report = build_feature_impact_analysis(data)
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_feature_impact_analysis(
    data: Sequence[dict[str, object]],
) -> dict[str, object]:
    expanded_data = enrich_dataset_with_microstructure_features(data)
    baseline_signals = generate_signal_v2(data)
    expanded_signals = generate_signal_v2(expanded_data)
    baseline_decisions = _generate_decisions(baseline_signals)
    expanded_decisions = _generate_decisions(expanded_signals)
    baseline_executions = tuple(
        simulate_execution(decision) for decision in baseline_decisions
    )
    expanded_executions = tuple(
        simulate_execution(decision) for decision in expanded_decisions
    )
    baseline_economic = _economic_report(data, baseline_signals, baseline_decisions)
    expanded_economic = _economic_report(
        expanded_data, expanded_signals, expanded_decisions
    )
    baseline_features = transform_market_features(data)
    expanded_features = _expanded_feature_set(data)
    baseline_importance = _feature_importance_proxy(data, baseline_features)
    expanded_importance = _feature_importance_proxy(data, expanded_features)
    baseline_metrics_v1 = build_metrics_v1(
        signals=baseline_signals,
        decisions=baseline_decisions,
        executions=baseline_executions,
    )
    expanded_metrics_v1 = build_metrics_v1(
        signals=expanded_signals,
        decisions=expanded_decisions,
        executions=expanded_executions,
    )
    predictive_delta = {
        "baseline_edge": _float_value(baseline_economic.get("edge_score")),
        "expanded_edge": _float_value(expanded_economic.get("edge_score")),
    }
    predictive_delta["delta"] = (
        predictive_delta["expanded_edge"] - predictive_delta["baseline_edge"]
    )
    sensitivity = _decision_sensitivity(
        baseline_signals=baseline_signals,
        expanded_signals=expanded_signals,
        baseline_decisions=baseline_decisions,
        expanded_decisions=expanded_decisions,
        baseline_metrics_v1=baseline_metrics_v1,
        expanded_metrics_v1=expanded_metrics_v1,
    )
    return {
        "dataset_rows": len(data),
        "symbols": len({str(row["symbol"]) for row in data}),
        "predictive_delta": predictive_delta,
        "information_gain_proxy": _information_gain_proxy(
            baseline_importance=baseline_importance,
            expanded_importance=expanded_importance,
            baseline_signals=baseline_signals,
            expanded_signals=expanded_signals,
        ),
        "decision_sensitivity_check": sensitivity,
        "stability_constraint": _stability_constraint(
            predictive_delta=predictive_delta,
            sensitivity=sensitivity,
            baseline_metrics_v1=baseline_metrics_v1,
            expanded_metrics_v1=expanded_metrics_v1,
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run feature impact analysis v1")
    parser.add_argument(
        "historical_data",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_feature_impact_analysis(
        args.historical_data, output_dir=args.output_dir
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _economic_report(
    data: Sequence[dict[str, object]],
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
) -> dict[str, object]:
    future_return_by_event_id = _future_returns_by_event_id(data)
    signal_by_id = {str(signal["signal_id"]): signal for signal in signals}
    rewards = tuple(
        _reward(
            signal=signal_by_id[str(decision["source_signal_id"])],
            decision=decision,
            future_return=future_return_by_event_id.get(
                str(signal_by_id[str(decision["source_signal_id"])]["source_event_id"]),
                0.0,
            ),
        )
        for decision in decisions
        if str(decision["source_signal_id"]) in signal_by_id
    )
    return _build_report(rewards)


def _expanded_feature_set(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    micro_by_event_id = {
        str(feature["event_id"]): feature
        for feature in transform_microstructure_features_v2(data)
    }
    return tuple(
        {
            **feature,
            **{
                key: value
                for key, value in micro_by_event_id[str(feature["event_id"])].items()
                if key not in IDENTITY_KEYS
            },
        }
        for feature in transform_market_features(data)
    )


def _feature_importance_proxy(
    data: Sequence[dict[str, object]],
    features: Sequence[dict[str, object]],
) -> dict[str, float]:
    outcome_by_event_id = _outcomes_by_event_id(data)
    outcome_sign_by_event_id = {
        event_id: _direction_sign(direction)
        for event_id, direction in outcome_by_event_id.items()
    }
    numeric_keys = sorted(
        {
            key
            for feature in features
            for key, value in feature.items()
            if key not in IDENTITY_KEYS and isinstance(value, int | float)
        }
    )
    importance = {}
    for key in numeric_keys:
        paired = tuple(
            (
                _float_value(feature.get(key)),
                outcome_sign_by_event_id[str(feature["event_id"])],
            )
            for feature in features
            if str(feature["event_id"]) in outcome_sign_by_event_id
        )
        importance[key] = abs(
            _correlation(
                tuple(item[0] for item in paired),
                tuple(item[1] for item in paired),
            )
        )
    return importance


def _information_gain_proxy(
    *,
    baseline_importance: Mapping[str, float],
    expanded_importance: Mapping[str, float],
    baseline_signals: Sequence[dict[str, object]],
    expanded_signals: Sequence[dict[str, object]],
) -> dict[str, object]:
    baseline_proxy = _mean(tuple(baseline_importance.values()))
    expanded_proxy = _mean(tuple(expanded_importance.values()))
    common_keys = tuple(sorted(set(baseline_importance) & set(expanded_importance)))
    common_deltas = tuple(
        abs(expanded_importance[key] - baseline_importance[key]) for key in common_keys
    )
    baseline_variance = _variance(_signal_values(baseline_signals))
    expanded_variance = _variance(_signal_values(expanded_signals))
    return {
        "baseline_mutual_information_proxy": baseline_proxy,
        "expanded_mutual_information_proxy": expanded_proxy,
        "mutual_information_proxy_change": expanded_proxy - baseline_proxy,
        "feature_importance_stability": {
            "common_feature_count": len(common_keys),
            "max_abs_common_importance_delta": max(common_deltas, default=0.0),
            "mean_abs_common_importance_delta": _mean(common_deltas),
        },
        "signal_variance_shift": {
            "baseline_signal_variance": baseline_variance,
            "expanded_signal_variance": expanded_variance,
            "delta": expanded_variance - baseline_variance,
        },
    }


def _decision_sensitivity(
    *,
    baseline_signals: Sequence[dict[str, object]],
    expanded_signals: Sequence[dict[str, object]],
    baseline_decisions: Sequence[dict[str, object]],
    expanded_decisions: Sequence[dict[str, object]],
    baseline_metrics_v1: Mapping[str, object],
    expanded_metrics_v1: Mapping[str, object],
) -> dict[str, object]:
    baseline_distribution = _decision_distribution(baseline_decisions)
    expanded_distribution = _decision_distribution(expanded_decisions)
    baseline_regimes = _regime_distribution(baseline_signals)
    expanded_regimes = _regime_distribution(expanded_signals)
    baseline_acceptance = _float_value(baseline_metrics_v1.get("acceptance_ratio"))
    expanded_acceptance = _float_value(expanded_metrics_v1.get("acceptance_ratio"))
    return {
        "decision_output_distribution_changed": baseline_distribution
        != expanded_distribution,
        "baseline_decision_distribution": baseline_distribution,
        "expanded_decision_distribution": expanded_distribution,
        "regime_routing_behavior_changed": baseline_regimes != expanded_regimes,
        "baseline_regime_distribution": baseline_regimes,
        "expanded_regime_distribution": expanded_regimes,
        "execution_acceptance_ratio_changed": baseline_acceptance
        != expanded_acceptance,
        "baseline_execution_acceptance_ratio": baseline_acceptance,
        "expanded_execution_acceptance_ratio": expanded_acceptance,
        "execution_acceptance_ratio_delta": expanded_acceptance - baseline_acceptance,
    }


def _stability_constraint(
    *,
    predictive_delta: Mapping[str, float],
    sensitivity: Mapping[str, object],
    baseline_metrics_v1: Mapping[str, object],
    expanded_metrics_v1: Mapping[str, object],
) -> dict[str, object]:
    changed_sections = []
    if predictive_delta["delta"] != 0.0:
        changed_sections.append("predictive_delta")
    if sensitivity["decision_output_distribution_changed"]:
        changed_sections.append("decision_distribution")
    if sensitivity["regime_routing_behavior_changed"]:
        changed_sections.append("regime_routing")
    if sensitivity["execution_acceptance_ratio_changed"]:
        changed_sections.append("execution_acceptance_ratio")
    if baseline_metrics_v1 != expanded_metrics_v1:
        changed_sections.append("metrics_v1")
    return {
        "confirmed": not changed_sections,
        "pipeline_behavior_changed": bool(changed_sections),
        "changed_sections": changed_sections,
        "no_change_except_numeric_sensitivity": not changed_sections,
    }


def _decision_distribution(
    decisions: Sequence[dict[str, object]],
) -> dict[str, int]:
    return dict(
        sorted(Counter(str(decision["direction"]) for decision in decisions).items())
    )


def _regime_distribution(
    signals: Sequence[dict[str, object]],
) -> dict[str, int]:
    return dict(
        sorted(Counter(str(signal["volatility_regime"]) for signal in signals).items())
    )


def _signal_values(signals: Sequence[dict[str, object]]) -> tuple[float, ...]:
    return tuple(_float_value(signal.get("signal_delta")) for signal in signals)


def _direction_sign(direction: str) -> float:
    if direction == "long":
        return 1.0
    return -1.0


def _correlation(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != len(second) or len(first) < 2:
        return 0.0
    first_std = _stddev(first)
    second_std = _stddev(second)
    if first_std == 0.0 or second_std == 0.0:
        return 0.0
    return _covariance(first, second) / (first_std * second_std)


def _covariance(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != len(second) or not first:
        return 0.0
    first_mean = _mean(first)
    second_mean = _mean(second)
    return _mean(
        tuple(
            (first_value - first_mean) * (second_value - second_mean)
            for first_value, second_value in zip(first, second, strict=True)
        )
    )


def _variance(values: Sequence[float]) -> float:
    stddev = _stddev(values)
    return stddev * stddev


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
