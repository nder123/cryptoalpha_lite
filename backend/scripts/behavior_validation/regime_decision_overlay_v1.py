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
from scripts.behavior_validation.metrics_v1 import build_metrics_v1
from scripts.behavior_validation.state_transition_model_v1 import load_state_labels

SUMMARY_FILENAME = "regime_decision_overlay_v1.json"
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
DEFAULT_STATE_LABEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "market_state_labeling_v1.json"
)
DEFAULT_TRANSITION_MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "state_transition_model_v1.json"
)
DEFAULT_STABILITY_MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "state_stability_model_v1.json"
)
DEFAULT_FORECASTABILITY_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "regime_forecastability_v1.json"
)
STRESS_WEIGHT = {
    "STABLE": 1.10,
    "TRANSITIONAL": 0.85,
    "CHAOTIC": 0.65,
}
MIN_REGIME_WEIGHT = 0.20
MAX_REGIME_WEIGHT = 1.20
PRE_SHIFT_WINDOW = 3


def run_regime_decision_overlay(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    *,
    state_labels_path: Path | str = DEFAULT_STATE_LABEL_PATH,
    transition_model_path: Path | str = DEFAULT_TRANSITION_MODEL_PATH,
    stability_model_path: Path | str = DEFAULT_STABILITY_MODEL_PATH,
    forecastability_path: Path | str = DEFAULT_FORECASTABILITY_PATH,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    labels = load_state_labels(state_labels_path)
    transition_model = _load_json_object(transition_model_path)
    stability_model = _load_json_object(stability_model_path)
    forecastability = _load_json_object(forecastability_path)
    report = build_regime_decision_overlay_report(
        data=data,
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        forecastability=forecastability,
    )
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_regime_decision_overlay_report(
    *,
    data: Sequence[dict[str, object]],
    labels: Sequence[dict[str, object]],
    transition_model: Mapping[str, object],
    stability_model: Mapping[str, object],
    forecastability: Mapping[str, object],
) -> dict[str, object]:
    signals = generate_signal_v2(data)
    baseline_decisions = _generate_decisions(signals)
    state_by_event_id = _state_by_event_id(labels)
    state_sequence_by_symbol = _state_sequence_by_symbol(labels)
    overlay_records = _overlay_records(
        signals=signals,
        decisions=baseline_decisions,
        state_by_event_id=state_by_event_id,
        forecastability=forecastability,
    )
    overlay_decisions = apply_regime_decision_overlay(
        decisions=baseline_decisions,
        overlay_records=overlay_records,
    )
    baseline = _mode_result(
        mode="BASELINE",
        data=data,
        signals=signals,
        decisions=baseline_decisions,
        labels=labels,
        state_sequence_by_symbol=state_sequence_by_symbol,
    )
    overlay = _mode_result(
        mode="OVERLAY",
        data=data,
        signals=signals,
        decisions=overlay_decisions,
        labels=labels,
        state_sequence_by_symbol=state_sequence_by_symbol,
    )
    return {
        "dataset_rows": len(data),
        "state_label_rows": len(labels),
        "symbols": len({str(row["symbol"]) for row in data}),
        "baseline": baseline,
        "overlay": overlay,
        "baseline_vs_overlay_comparison": _comparison(baseline, overlay),
        "regime_exposure_heatmap": _regime_exposure_heatmap(overlay_records),
        "stability_improvement_metrics": _stability_improvement_metrics(
            baseline_records=_decision_records(
                signals=signals,
                decisions=baseline_decisions,
                state_by_event_id=state_by_event_id,
                state_sequence_by_symbol=state_sequence_by_symbol,
            ),
            overlay_records=_decision_records(
                signals=signals,
                decisions=overlay_decisions,
                state_by_event_id=state_by_event_id,
                state_sequence_by_symbol=state_sequence_by_symbol,
            ),
        ),
        "transition_sensitivity_improvement": _transition_sensitivity_improvement(
            baseline_records=_decision_records(
                signals=signals,
                decisions=baseline_decisions,
                state_by_event_id=state_by_event_id,
                state_sequence_by_symbol=state_sequence_by_symbol,
            ),
            overlay_records=_decision_records(
                signals=signals,
                decisions=overlay_decisions,
                state_by_event_id=state_by_event_id,
                state_sequence_by_symbol=state_sequence_by_symbol,
            ),
        ),
        "trade_concentration_by_regime": _trade_concentration_by_regime(
            _decision_records(
                signals=signals,
                decisions=overlay_decisions,
                state_by_event_id=state_by_event_id,
                state_sequence_by_symbol=state_sequence_by_symbol,
            )
        ),
        "regime_weight_summary": _regime_weight_summary(overlay_records),
        "artifact_consistency": _artifact_consistency(
            labels=labels,
            transition_model=transition_model,
            stability_model=stability_model,
            forecastability=forecastability,
        ),
        "validation": {
            "uses_existing_evaluation_runner_decisions": True,
            "evaluation_engine_modified": False,
            "economic_closure_modified": False,
            "features_modified": False,
            "new_features_created": False,
            "dataset_modified": False,
            "transition_model_modified": False,
            "ml_model_used": False,
            "optimization_loop_used": False,
            "binary_gating_used": False,
            "direction_changes": _direction_changes(
                baseline_decisions, overlay_decisions
            ),
        },
    }


def apply_regime_decision_overlay(
    *,
    decisions: Sequence[dict[str, object]],
    overlay_records: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    weight_by_signal_id = {
        str(record["source_signal_id"]): _float_value(record.get("regime_weight"))
        for record in overlay_records
    }
    return tuple(
        {
            **decision,
            "decision_score": _float_value(decision.get("decision_score"))
            * weight_by_signal_id[str(decision["source_signal_id"])],
        }
        for decision in decisions
        if str(decision["source_signal_id"]) in weight_by_signal_id
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run regime decision overlay v1")
    parser.add_argument(
        "historical_data",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--state-labels",
        type=Path,
        default=DEFAULT_STATE_LABEL_PATH,
    )
    parser.add_argument(
        "--transition-model",
        type=Path,
        default=DEFAULT_TRANSITION_MODEL_PATH,
    )
    parser.add_argument(
        "--stability-model",
        type=Path,
        default=DEFAULT_STABILITY_MODEL_PATH,
    )
    parser.add_argument(
        "--forecastability",
        type=Path,
        default=DEFAULT_FORECASTABILITY_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_regime_decision_overlay(
        args.historical_data,
        state_labels_path=args.state_labels,
        transition_model_path=args.transition_model,
        stability_model_path=args.stability_model,
        forecastability_path=args.forecastability,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _overlay_records(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    state_by_event_id: Mapping[str, Mapping[str, object]],
    forecastability: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    decision_by_signal_id = {
        str(decision["source_signal_id"]): decision for decision in decisions
    }
    return tuple(
        {
            "source_signal_id": signal["signal_id"],
            "symbol": signal.get("symbol"),
            "timestamp": signal.get("timestamp"),
            "state": _state_key(state_by_event_id[str(signal["source_event_id"])]),
            "volatility_state": _state_dimension(
                state_by_event_id[str(signal["source_event_id"])],
                "volatility",
            ),
            "trend_state": _state_dimension(
                state_by_event_id[str(signal["source_event_id"])],
                "trend",
            ),
            "stress_state": _state_dimension(
                state_by_event_id[str(signal["source_event_id"])],
                "stress",
            ),
            "base_score": _float_value(
                decision_by_signal_id[str(signal["signal_id"])].get("decision_score")
            ),
            "regime_weight": _regime_weight(
                state=_state_key(state_by_event_id[str(signal["source_event_id"])]),
                state_payload=state_by_event_id[str(signal["source_event_id"])],
                forecastability=forecastability,
            ),
        }
        for signal in signals
        if str(signal["source_event_id"]) in state_by_event_id
        and str(signal["signal_id"]) in decision_by_signal_id
    )


def _regime_weight(
    *,
    state: str,
    state_payload: Mapping[str, object],
    forecastability: Mapping[str, object],
) -> float:
    stress_state = _state_dimension(state_payload, "stress")
    base_weight = STRESS_WEIGHT.get(stress_state, 0.85)
    state_forecastability = _mapping(
        _mapping(forecastability.get("forecastability_score_per_state")).get(state)
    )
    stay_probability = _float_value(state_forecastability.get("stay_probability"))
    transition_risk = _float_value(
        state_forecastability.get("one_step_transition_risk")
    )
    if stay_probability >= 0.70:
        base_weight += 0.05
    if stay_probability < 0.50:
        base_weight -= 0.10
    if transition_risk >= 0.50:
        base_weight -= 0.10
    return min(MAX_REGIME_WEIGHT, max(MIN_REGIME_WEIGHT, base_weight))


def _mode_result(
    *,
    mode: str,
    data: Sequence[dict[str, object]],
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    labels: Sequence[dict[str, object]],
    state_sequence_by_symbol: Mapping[str, Sequence[tuple[str, str]]],
) -> dict[str, object]:
    executions = tuple(simulate_execution(decision) for decision in decisions)
    metrics_v1 = build_metrics_v1(
        signals=signals,
        decisions=decisions,
        executions=executions,
    )
    economic_report = _economic_report(data, signals, decisions)
    rewards = _economic_rewards(data, signals, decisions)
    records = _decision_records(
        signals=signals,
        decisions=decisions,
        state_by_event_id=_state_by_event_id(labels),
        state_sequence_by_symbol=state_sequence_by_symbol,
    )
    drawdown = _drawdown(rewards)
    return {
        "mode": mode,
        "edge": economic_report["edge_score"],
        "cost_adjusted_pnl": economic_report["cost_adjusted_pnl"],
        "total_pnl": economic_report["total_pnl"],
        "max_drawdown": drawdown["max_drawdown"],
        "ending_equity": drawdown["ending_equity"],
        "acceptance_ratio": metrics_v1["acceptance_ratio"],
        "decision_distribution": _decision_distribution(decisions),
        "regime_pnl": economic_report["regime_pnl"],
        "regime_exposure_distribution": _regime_exposure_distribution(records),
    }


def _economic_report(
    data: Sequence[dict[str, object]],
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
) -> dict[str, object]:
    return _build_report(_economic_rewards(data, signals, decisions))


def _economic_rewards(
    data: Sequence[dict[str, object]],
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
) -> tuple[dict[str, float | str], ...]:
    future_return_by_event_id = _future_returns_by_event_id(data)
    signal_by_id = {str(signal["signal_id"]): signal for signal in signals}
    return tuple(
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


def _decision_records(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    state_by_event_id: Mapping[str, Mapping[str, object]],
    state_sequence_by_symbol: Mapping[str, Sequence[tuple[str, str]]],
) -> tuple[dict[str, object], ...]:
    signal_by_id = {str(signal["signal_id"]): signal for signal in signals}
    state_index_by_symbol = _state_index_by_symbol(state_sequence_by_symbol)
    records = []
    for decision in decisions:
        signal = signal_by_id.get(str(decision["source_signal_id"]))
        if signal is None:
            continue
        event_id = str(signal["source_event_id"])
        if event_id not in state_by_event_id:
            continue
        symbol = str(signal.get("symbol"))
        timestamp = str(signal.get("timestamp"))
        state = _state_key(state_by_event_id[event_id])
        index = state_index_by_symbol.get((symbol, timestamp), -1)
        records.append(
            {
                "symbol": symbol,
                "timestamp": timestamp,
                "state": state,
                "volatility_state": _state_dimension(
                    state_by_event_id[event_id], "volatility"
                ),
                "trend_state": _state_dimension(state_by_event_id[event_id], "trend"),
                "stress_state": _state_dimension(state_by_event_id[event_id], "stress"),
                "score_abs": abs(_float_value(decision.get("decision_score"))),
                "pre_shift": _is_pre_shift(
                    symbol=symbol,
                    index=index,
                    sequence_by_symbol=state_sequence_by_symbol,
                ),
            }
        )
    return tuple(records)


def _comparison(
    baseline: Mapping[str, object],
    overlay: Mapping[str, object],
) -> dict[str, float | bool]:
    baseline_edge = _float_value(baseline.get("edge"))
    overlay_edge = _float_value(overlay.get("edge"))
    baseline_cost = _float_value(baseline.get("cost_adjusted_pnl"))
    overlay_cost = _float_value(overlay.get("cost_adjusted_pnl"))
    baseline_drawdown = _float_value(baseline.get("max_drawdown"))
    overlay_drawdown = _float_value(overlay.get("max_drawdown"))
    return {
        "edge_delta": overlay_edge - baseline_edge,
        "cost_adjusted_pnl_delta": overlay_cost - baseline_cost,
        "total_pnl_delta": _float_value(overlay.get("total_pnl"))
        - _float_value(baseline.get("total_pnl")),
        "max_drawdown_delta": overlay_drawdown - baseline_drawdown,
        "drawdown_reduction": baseline_drawdown - overlay_drawdown,
        "risk_adjusted_pnl_delta": (overlay_cost / max(overlay_drawdown, 1e-12))
        - (baseline_cost / max(baseline_drawdown, 1e-12)),
        "risk_reduced": overlay_drawdown < baseline_drawdown,
    }


def _regime_exposure_heatmap(
    overlay_records: Sequence[dict[str, object]],
) -> dict[str, dict[str, dict[str, float | int]]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for record in overlay_records:
        row = str(record["volatility_state"])
        column = f"{record['trend_state']}|{record['stress_state']}"
        grouped[row][column].append(
            _float_value(record.get("base_score"))
            * _float_value(record.get("regime_weight"))
        )
    return {
        row: {
            column: {
                "count": len(values),
                "mean_abs_exposure": _mean_abs(tuple(values)),
                "total_abs_exposure": sum(abs(value) for value in values),
            }
            for column, values in sorted(columns.items())
        }
        for row, columns in sorted(grouped.items())
    }


def _stability_improvement_metrics(
    *,
    baseline_records: Sequence[dict[str, object]],
    overlay_records: Sequence[dict[str, object]],
) -> dict[str, object]:
    baseline_by_stress = _exposure_by_key(baseline_records, "stress_state")
    overlay_by_stress = _exposure_by_key(overlay_records, "stress_state")
    chaotic_baseline = _float_value(
        _mapping(baseline_by_stress.get("CHAOTIC")).get("mean_abs_exposure")
    )
    chaotic_overlay = _float_value(
        _mapping(overlay_by_stress.get("CHAOTIC")).get("mean_abs_exposure")
    )
    stable_baseline = _float_value(
        _mapping(baseline_by_stress.get("STABLE")).get("mean_abs_exposure")
    )
    stable_overlay = _float_value(
        _mapping(overlay_by_stress.get("STABLE")).get("mean_abs_exposure")
    )
    return {
        "baseline_exposure_by_stress": baseline_by_stress,
        "overlay_exposure_by_stress": overlay_by_stress,
        "chaotic_exposure_reduction": chaotic_baseline - chaotic_overlay,
        "stable_exposure_delta": stable_overlay - stable_baseline,
        "risk_reduced_in_chaotic_regimes": chaotic_overlay < chaotic_baseline,
        "stable_regime_not_degraded": stable_overlay >= stable_baseline,
    }


def _transition_sensitivity_improvement(
    *,
    baseline_records: Sequence[dict[str, object]],
    overlay_records: Sequence[dict[str, object]],
) -> dict[str, object]:
    baseline_pre_shift = _mean_record_exposure(
        tuple(record for record in baseline_records if bool(record["pre_shift"]))
    )
    baseline_stable = _mean_record_exposure(
        tuple(record for record in baseline_records if not bool(record["pre_shift"]))
    )
    overlay_pre_shift = _mean_record_exposure(
        tuple(record for record in overlay_records if bool(record["pre_shift"]))
    )
    overlay_stable = _mean_record_exposure(
        tuple(record for record in overlay_records if not bool(record["pre_shift"]))
    )
    baseline_ratio = baseline_pre_shift / baseline_stable if baseline_stable else 0.0
    overlay_ratio = overlay_pre_shift / overlay_stable if overlay_stable else 0.0
    return {
        "baseline_pre_shift_mean_abs_exposure": baseline_pre_shift,
        "overlay_pre_shift_mean_abs_exposure": overlay_pre_shift,
        "baseline_stable_window_mean_abs_exposure": baseline_stable,
        "overlay_stable_window_mean_abs_exposure": overlay_stable,
        "pre_shift_exposure_delta": overlay_pre_shift - baseline_pre_shift,
        "pre_shift_vs_stable_ratio_delta": overlay_ratio - baseline_ratio,
        "unstable_transition_exposure_reduced": overlay_pre_shift < baseline_pre_shift,
    }


def _trade_concentration_by_regime(
    records: Sequence[dict[str, object]],
) -> dict[str, dict[str, float | int]]:
    total_abs = sum(_float_value(record.get("score_abs")) for record in records)
    grouped: dict[str, list[float]] = defaultdict(list)
    for record in records:
        grouped[str(record["state"])].append(_float_value(record.get("score_abs")))
    return {
        state: {
            "count": len(values),
            "total_abs_exposure": sum(values),
            "share_of_abs_exposure": sum(values) / total_abs if total_abs else 0.0,
            "mean_abs_exposure": _mean(tuple(values)),
        }
        for state, values in sorted(grouped.items())
    }


def _regime_weight_summary(
    overlay_records: Sequence[dict[str, object]],
) -> dict[str, object]:
    weights = tuple(
        _float_value(record.get("regime_weight")) for record in overlay_records
    )
    return {
        "count": len(weights),
        "mean_weight": _mean(weights),
        "min_weight": min(weights, default=1.0),
        "max_weight": max(weights, default=1.0),
        "weight_by_stress": _weight_by_key(overlay_records, "stress_state"),
        "weight_by_state": _weight_by_key(overlay_records, "state"),
    }


def _artifact_consistency(
    *,
    labels: Sequence[dict[str, object]],
    transition_model: Mapping[str, object],
    stability_model: Mapping[str, object],
    forecastability: Mapping[str, object],
) -> dict[str, bool]:
    unique_states = len({_state_key(label) for label in labels})
    return {
        "state_rows_match_stability": len(labels)
        == int(_float_value(stability_model.get("state_label_rows"))),
        "unique_states_match_transition": unique_states
        == int(_float_value(transition_model.get("unique_states"))),
        "unique_states_match_forecastability": unique_states
        == int(_float_value(forecastability.get("unique_states"))),
        "forecastability_above_random": bool(
            _mapping(forecastability.get("global_forecastability_index")).get(
                "forecastability_above_random"
            )
        ),
    }


def _drawdown(rewards: Sequence[dict[str, float | str]]) -> dict[str, float]:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for reward in rewards:
        equity += _float_value(reward.get("net_pnl"))
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return {"ending_equity": equity, "max_drawdown": max_drawdown}


def _regime_exposure_distribution(
    records: Sequence[dict[str, object]],
) -> dict[str, object]:
    return {
        "by_state": _exposure_by_key(records, "state"),
        "by_stress": _exposure_by_key(records, "stress_state"),
        "by_volatility": _exposure_by_key(records, "volatility_state"),
        "by_trend": _exposure_by_key(records, "trend_state"),
    }


def _exposure_by_key(
    records: Sequence[dict[str, object]],
    key: str,
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for record in records:
        grouped[str(record[key])].append(_float_value(record.get("score_abs")))
    return {
        value: {
            "count": len(exposures),
            "mean_abs_exposure": _mean(tuple(exposures)),
            "total_abs_exposure": sum(exposures),
        }
        for value, exposures in sorted(grouped.items())
    }


def _weight_by_key(
    records: Sequence[dict[str, object]],
    key: str,
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for record in records:
        grouped[str(record[key])].append(_float_value(record.get("regime_weight")))
    return {
        value: {
            "count": len(weights),
            "mean_weight": _mean(tuple(weights)),
            "min_weight": min(weights),
            "max_weight": max(weights),
        }
        for value, weights in sorted(grouped.items())
    }


def _state_by_event_id(
    labels: Sequence[dict[str, object]],
) -> dict[str, Mapping[str, object]]:
    return {str(label["event_id"]): _mapping(label.get("state")) for label in labels}


def _state_sequence_by_symbol(
    labels: Sequence[dict[str, object]],
) -> dict[str, tuple[tuple[str, str], ...]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for label in labels:
        grouped[str(label["symbol"])].append(label)
    return {
        symbol: tuple(
            (str(label["timestamp"]), _state_key(label))
            for label in sorted(symbol_labels, key=lambda item: str(item["timestamp"]))
        )
        for symbol, symbol_labels in sorted(grouped.items())
    }


def _state_index_by_symbol(
    sequence_by_symbol: Mapping[str, Sequence[tuple[str, str]]],
) -> dict[tuple[str, str], int]:
    return {
        (symbol, timestamp): index
        for symbol, sequence in sequence_by_symbol.items()
        for index, (timestamp, _) in enumerate(sequence)
    }


def _is_pre_shift(
    *,
    symbol: str,
    index: int,
    sequence_by_symbol: Mapping[str, Sequence[tuple[str, str]]],
) -> bool:
    sequence = sequence_by_symbol.get(symbol, ())
    if index < 0 or index >= len(sequence) - 1:
        return False
    current_state = sequence[index][1]
    future_states = tuple(
        state for _, state in sequence[index + 1 : index + PRE_SHIFT_WINDOW + 1]
    )
    return any(state != current_state for state in future_states)


def _decision_distribution(decisions: Sequence[dict[str, object]]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(decision["direction"]) for decision in decisions).items())
    )


def _direction_changes(
    baseline_decisions: Sequence[dict[str, object]],
    overlay_decisions: Sequence[dict[str, object]],
) -> int:
    return sum(
        1
        for baseline_decision, overlay_decision in zip(
            baseline_decisions,
            overlay_decisions,
            strict=True,
        )
        if baseline_decision["direction"] != overlay_decision["direction"]
    )


def _state_key(label_or_state: Mapping[str, object]) -> str:
    if "state" in label_or_state and isinstance(label_or_state["state"], dict):
        state = _mapping(label_or_state["state"])
    else:
        state = label_or_state
    return "_".join(
        str(state.get(key, "UNKNOWN")) for key in ("volatility", "trend", "stress")
    )


def _state_dimension(state: Mapping[str, object], key: str) -> str:
    return str(state.get(key, "UNKNOWN"))


def _load_json_object(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Regime decision overlay requires JSON object artifacts")
    return payload


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _mean_record_exposure(records: Sequence[dict[str, object]]) -> float:
    return _mean(tuple(_float_value(record.get("score_abs")) for record in records))


def _mean_abs(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(abs(value) for value in values) / len(values)


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
