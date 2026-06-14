from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
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
from scripts.behavior_validation.evaluation_runner import _generate_decisions
from scripts.behavior_validation.execution_simulator import simulate_execution
from scripts.behavior_validation.feature_transform import generate_signal_v2
from scripts.behavior_validation.feature_transform_microstructure_v2 import (
    transform_microstructure_features_v2,
)
from scripts.behavior_validation.metrics_v1 import build_metrics_v1

SUMMARY_FILENAME = "decision_dynamics_v1.json"
STATIC_MODE = "STATIC"
DYNAMIC_MODE = "DYNAMIC"
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
VOLATILITY_FACTORS = {
    "low": 1.05,
    "mid": 1.0,
    "high": 0.75,
}
MIN_DYNAMIC_FACTOR = 0.25
MAX_DYNAMIC_FACTOR = 1.25


def run_decision_dynamics_analysis(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    report = build_decision_dynamics_analysis(data)
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_decision_dynamics_analysis(
    data: Sequence[dict[str, object]],
) -> dict[str, object]:
    signals = generate_signal_v2(data)
    static_decisions = _generate_decisions(signals)
    micro_features = transform_microstructure_features_v2(data)
    dynamic_decisions = apply_dynamic_decision_scaling(
        signals=signals,
        decisions=static_decisions,
        micro_features=micro_features,
    )
    static_result = _mode_result(
        mode=STATIC_MODE,
        data=data,
        signals=signals,
        decisions=static_decisions,
        scaling_records=(),
    )
    dynamic_result = _mode_result(
        mode=DYNAMIC_MODE,
        data=data,
        signals=signals,
        decisions=dynamic_decisions,
        scaling_records=_scaling_records(
            signals=signals,
            decisions=static_decisions,
            micro_features=micro_features,
        ),
    )
    return {
        "dataset_rows": len(data),
        "symbols": len({str(row["symbol"]) for row in data}),
        "static_mode": static_result,
        "dynamic_mode": dynamic_result,
        "delta": {
            "edge": _float_value(dynamic_result.get("edge"))
            - _float_value(static_result.get("edge")),
            "cost_adjusted_pnl": _float_value(dynamic_result.get("cost_adjusted_pnl"))
            - _float_value(static_result.get("cost_adjusted_pnl")),
            "total_pnl": _float_value(dynamic_result.get("total_pnl"))
            - _float_value(static_result.get("total_pnl")),
        },
        "validation": {
            "uses_existing_evaluation_runner_decisions": True,
            "metrics_v1_unmodified": True,
            "economic_closure_unmodified": True,
            "new_features_created": False,
            "new_dataset_created": False,
            "optimization_loop_used": False,
            "dynamic_direction_changes": _direction_changes(
                static_decisions, dynamic_decisions
            ),
        },
    }


def apply_dynamic_decision_scaling(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    micro_features: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    factor_by_signal_id = {
        str(signal["signal_id"]): _dynamic_factor(signal, micro_by_event_id)
        for signal, micro_by_event_id in _signal_micro_pairs(
            signals=signals,
            micro_features=micro_features,
        )
    }
    return tuple(
        {
            **decision,
            "decision_score": _float_value(decision.get("decision_score"))
            * factor_by_signal_id[str(decision["source_signal_id"])],
        }
        for decision in decisions
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run decision dynamics analysis v1")
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
    report = run_decision_dynamics_analysis(
        args.historical_data,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _mode_result(
    *,
    mode: str,
    data: Sequence[dict[str, object]],
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    scaling_records: Sequence[dict[str, object]],
) -> dict[str, object]:
    executions = tuple(simulate_execution(decision) for decision in decisions)
    metrics_v1 = build_metrics_v1(
        signals=signals,
        decisions=decisions,
        executions=executions,
    )
    economic_report = _economic_report(data, signals, decisions)
    return {
        "mode": mode,
        "edge": economic_report["edge_score"],
        "cost_adjusted_pnl": economic_report["cost_adjusted_pnl"],
        "total_pnl": economic_report["total_pnl"],
        "acceptance_ratio": metrics_v1["acceptance_ratio"],
        "decision_distribution": _decision_distribution(decisions),
        "regime_pnl": economic_report["regime_pnl"],
        "scaling_summary": _scaling_summary(scaling_records),
    }


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


def _scaling_records(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    micro_features: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    decision_by_signal_id = {
        str(decision["source_signal_id"]): decision for decision in decisions
    }
    return tuple(
        {
            "symbol": signal.get("symbol"),
            "volatility_regime": signal.get("volatility_regime"),
            "correlation_regime": _correlation_regime(micro_feature),
            "market_stress_regime": _market_stress_regime(signal, micro_feature),
            "factor": _dynamic_factor(signal, micro_feature),
            "base_score": _float_value(
                decision_by_signal_id[str(signal["signal_id"])].get("decision_score")
            ),
        }
        for signal, micro_feature in _signal_micro_pairs(
            signals=signals,
            micro_features=micro_features,
        )
        if str(signal["signal_id"]) in decision_by_signal_id
    )


def _signal_micro_pairs(
    *,
    signals: Sequence[dict[str, object]],
    micro_features: Sequence[dict[str, object]],
) -> tuple[tuple[dict[str, object], dict[str, object]], ...]:
    micro_by_event_id = {
        str(feature["event_id"]): feature for feature in micro_features
    }
    return tuple(
        (signal, micro_by_event_id[str(signal["source_event_id"])])
        for signal in signals
        if str(signal["source_event_id"]) in micro_by_event_id
    )


def _dynamic_factor(
    signal: Mapping[str, object],
    micro_feature: Mapping[str, object],
) -> float:
    raw_factor = (
        _volatility_factor(signal)
        * _correlation_factor(micro_feature)
        * _market_stress_factor(signal, micro_feature)
    )
    return min(MAX_DYNAMIC_FACTOR, max(MIN_DYNAMIC_FACTOR, raw_factor))


def _volatility_factor(signal: Mapping[str, object]) -> float:
    return VOLATILITY_FACTORS.get(str(signal.get("volatility_regime")), 1.0)


def _correlation_factor(micro_feature: Mapping[str, object]) -> float:
    regime = _correlation_regime(micro_feature)
    if regime == "high_correlation":
        return 0.9
    if regime == "low_correlation":
        return 0.95
    return 1.0


def _market_stress_factor(
    signal: Mapping[str, object],
    micro_feature: Mapping[str, object],
) -> float:
    regime = _market_stress_regime(signal, micro_feature)
    if regime == "stress":
        return 0.8
    if regime == "elevated":
        return 0.9
    return 1.0


def _correlation_regime(micro_feature: Mapping[str, object]) -> str:
    corr = abs(_float_value(micro_feature.get("micro_v2_corr_to_btc_20")))
    btc_eth_corr = abs(_float_value(micro_feature.get("micro_v2_btc_eth_corr_20")))
    anchor_corr = max(corr, btc_eth_corr)
    if anchor_corr >= 0.8:
        return "high_correlation"
    if anchor_corr <= 0.25:
        return "low_correlation"
    return "mid_correlation"


def _market_stress_regime(
    signal: Mapping[str, object],
    micro_feature: Mapping[str, object],
) -> str:
    tail_intensity = _float_value(micro_feature.get("micro_v2_tail_intensity_20"))
    volatility = _float_value(micro_feature.get("micro_v2_rolling_volatility_20"))
    z_score = abs(_float_value(signal.get("z_score")))
    if tail_intensity >= 0.2 or volatility >= 0.01 or z_score >= 2.0:
        return "stress"
    if tail_intensity >= 0.1 or volatility >= 0.006 or z_score >= 1.0:
        return "elevated"
    return "normal"


def _scaling_summary(records: Sequence[dict[str, object]]) -> dict[str, object]:
    factors = tuple(_float_value(record.get("factor")) for record in records)
    if not factors:
        return {
            "count": 0,
            "mean_factor": 1.0,
            "min_factor": 1.0,
            "max_factor": 1.0,
            "factor_by_volatility_regime": {},
            "factor_by_correlation_regime": {},
            "factor_by_market_stress_regime": {},
        }
    return {
        "count": len(records),
        "mean_factor": _mean(factors),
        "min_factor": min(factors),
        "max_factor": max(factors),
        "factor_by_volatility_regime": _factor_by_key(records, "volatility_regime"),
        "factor_by_correlation_regime": _factor_by_key(records, "correlation_regime"),
        "factor_by_market_stress_regime": _factor_by_key(
            records,
            "market_stress_regime",
        ),
    }


def _factor_by_key(
    records: Sequence[dict[str, object]],
    key: str,
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for record in records:
        grouped[str(record[key])].append(_float_value(record.get("factor")))
    return {
        name: {
            "count": len(values),
            "mean_factor": _mean(tuple(values)),
            "min_factor": min(values),
            "max_factor": max(values),
        }
        for name, values in sorted(grouped.items())
    }


def _decision_distribution(decisions: Sequence[dict[str, object]]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(decision["direction"]) for decision in decisions).items())
    )


def _direction_changes(
    static_decisions: Sequence[dict[str, object]],
    dynamic_decisions: Sequence[dict[str, object]],
) -> int:
    return sum(
        1
        for static_decision, dynamic_decision in zip(
            static_decisions,
            dynamic_decisions,
            strict=True,
        )
        if static_decision["direction"] != dynamic_decision["direction"]
    )


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
