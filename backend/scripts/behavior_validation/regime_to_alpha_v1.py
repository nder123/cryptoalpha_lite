from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.behavior_validation.state_transition_model_v1 import load_state_labels

SUMMARY_FILENAME = "regime_to_alpha_v1.json"
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
DEFAULT_DECISION_OVERLAY_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "regime_decision_overlay_v1.json"
)
DIRECTION_BIAS = {
    "UP": 1.0,
    "DOWN": -1.0,
    "FLAT": 0.0,
}


def run_regime_to_alpha_translation(
    state_labels_path: Path | str = DEFAULT_STATE_LABEL_PATH,
    *,
    transition_model_path: Path | str = DEFAULT_TRANSITION_MODEL_PATH,
    stability_model_path: Path | str = DEFAULT_STABILITY_MODEL_PATH,
    forecastability_path: Path | str = DEFAULT_FORECASTABILITY_PATH,
    decision_overlay_path: Path | str = DEFAULT_DECISION_OVERLAY_PATH,
    output_dir: Path | None = None,
) -> dict[str, object]:
    labels = load_state_labels(state_labels_path)
    transition_model = _load_json_object(transition_model_path)
    stability_model = _load_json_object(stability_model_path)
    forecastability = _load_json_object(forecastability_path)
    decision_overlay = _load_json_object(decision_overlay_path)
    report = build_regime_to_alpha_report(
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        forecastability=forecastability,
        decision_overlay=decision_overlay,
    )
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_regime_to_alpha_report(
    *,
    labels: Sequence[dict[str, object]],
    transition_model: Mapping[str, object],
    stability_model: Mapping[str, object],
    forecastability: Mapping[str, object],
    decision_overlay: Mapping[str, object],
) -> dict[str, object]:
    state_counts = _state_counts(labels)
    total_labels = sum(state_counts.values())
    state_space = tuple(sorted(state_counts))
    transition_cost_unit = _transition_cost_unit(decision_overlay)
    alpha_by_state = {
        state: _state_alpha(
            state=state,
            count=count,
            total_labels=total_labels,
            transition_cost_unit=transition_cost_unit,
            stability_model=stability_model,
            forecastability=forecastability,
            decision_overlay=decision_overlay,
        )
        for state, count in state_counts.items()
    }
    return {
        "input_rows": total_labels,
        "unique_states": len(state_space),
        "alpha_per_state": dict(sorted(alpha_by_state.items())),
        "weighted_system_alpha": _weighted_system_alpha(alpha_by_state),
        "transition_cost_breakdown": _transition_cost_breakdown(
            alpha_by_state,
            transition_cost_unit,
        ),
        "stability_contribution": _stability_contribution(alpha_by_state),
        "comparison_vs_naive_baseline": _comparison_vs_naive(alpha_by_state),
        "regime_exposure_contribution": _regime_exposure_contribution(alpha_by_state),
        "final_system_alpha_score": _weighted_system_alpha(alpha_by_state)[
            "stability_weighted_system_alpha"
        ],
        "artifact_consistency": _artifact_consistency(
            labels=labels,
            state_space=state_space,
            transition_model=transition_model,
            stability_model=stability_model,
            forecastability=forecastability,
            decision_overlay=decision_overlay,
        ),
        "source_constraints": {
            "input_layers": (
                "market_state_labeling_v1",
                "state_transition_model_v1",
                "state_stability_model_v1",
                "regime_forecastability_v1",
                "regime_decision_overlay_v1",
            ),
            "new_data_used": False,
            "new_features_created": False,
            "execution_layer_modified": False,
            "evaluation_runner_modified": False,
            "economic_closure_modified": False,
            "learning_model_used": False,
            "optimization_used": False,
            "trading_logic_used": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run regime-to-alpha v1")
    parser.add_argument(
        "state_labels",
        nargs="?",
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
        "--decision-overlay",
        type=Path,
        default=DEFAULT_DECISION_OVERLAY_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_regime_to_alpha_translation(
        args.state_labels,
        transition_model_path=args.transition_model,
        stability_model_path=args.stability_model,
        forecastability_path=args.forecastability,
        decision_overlay_path=args.decision_overlay,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _state_alpha(
    *,
    state: str,
    count: int,
    total_labels: int,
    transition_cost_unit: float,
    stability_model: Mapping[str, object],
    forecastability: Mapping[str, object],
    decision_overlay: Mapping[str, object],
) -> dict[str, float | str | bool | int]:
    state_parts = _state_parts(state)
    probability = count / total_labels if total_labels else 0.0
    direction_bias = DIRECTION_BIAS.get(state_parts["trend"], 0.0)
    raw_stability_score = _state_stability_score(stability_model, state)
    bounded_stability_score = _bounded_stability_score(raw_stability_score)
    forecastability_metrics = _mapping(
        _mapping(forecastability.get("forecastability_score_per_state")).get(state)
    )
    predictability_score = _float_value(
        forecastability_metrics.get("forecastability_score")
    )
    stay_probability = _float_value(forecastability_metrics.get("stay_probability"))
    transition_probability = _float_value(
        forecastability_metrics.get("one_step_transition_risk")
    )
    exposure = _state_exposure(decision_overlay, state)
    exposure_share = _float_value(exposure.get("share_of_abs_exposure"))
    mean_exposure = _float_value(exposure.get("mean_abs_exposure"))
    regime_conditional_edge = direction_bias * predictability_score * mean_exposure
    transition_penalty = transition_cost_unit * transition_probability
    transition_adjusted_expectancy = (
        regime_conditional_edge * stay_probability - transition_penalty
    )
    stability_weighted_alpha = (
        bounded_stability_score * predictability_score * direction_bias
    )
    system_alpha_contribution = probability * stability_weighted_alpha
    regime_exposure_contribution = exposure_share * stability_weighted_alpha
    return {
        "count": count,
        "state_probability": probability,
        "direction_bias": direction_bias,
        "stability_score": raw_stability_score,
        "bounded_stability_score": bounded_stability_score,
        "predictability_score": predictability_score,
        "stay_probability": stay_probability,
        "transition_probability": transition_probability,
        "mean_abs_exposure": mean_exposure,
        "exposure_share": exposure_share,
        "regime_conditional_edge": regime_conditional_edge,
        "transition_penalty": transition_penalty,
        "transition_adjusted_expectancy": transition_adjusted_expectancy,
        "stability_weighted_alpha": stability_weighted_alpha,
        "system_alpha_contribution": system_alpha_contribution,
        "regime_exposure_contribution": regime_exposure_contribution,
        "alpha_sign": _alpha_sign(stability_weighted_alpha),
    }


def _weighted_system_alpha(
    alpha_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, float | bool]:
    stability_alpha = sum(
        _float_value(values.get("system_alpha_contribution"))
        for values in alpha_by_state.values()
    )
    regime_adjusted_expectancy = sum(
        _float_value(values.get("state_probability"))
        * _float_value(values.get("transition_adjusted_expectancy"))
        for values in alpha_by_state.values()
    )
    positive = sum(
        _float_value(values.get("system_alpha_contribution"))
        for values in alpha_by_state.values()
        if _float_value(values.get("system_alpha_contribution")) > 0.0
    )
    negative = sum(
        _float_value(values.get("system_alpha_contribution"))
        for values in alpha_by_state.values()
        if _float_value(values.get("system_alpha_contribution")) < 0.0
    )
    return {
        "stability_weighted_system_alpha": stability_alpha,
        "transition_adjusted_system_expectancy": regime_adjusted_expectancy,
        "positive_alpha_contribution": positive,
        "negative_alpha_contribution": negative,
        "has_positive_and_negative_regimes": positive > 0.0 and negative < 0.0,
    }


def _transition_cost_breakdown(
    alpha_by_state: Mapping[str, Mapping[str, object]],
    transition_cost_unit: float,
) -> dict[str, object]:
    weighted_transition_penalty = sum(
        _float_value(values.get("state_probability"))
        * _float_value(values.get("transition_penalty"))
        for values in alpha_by_state.values()
    )
    weighted_raw_abs_expectancy = sum(
        _float_value(values.get("state_probability"))
        * abs(_float_value(values.get("regime_conditional_edge")))
        for values in alpha_by_state.values()
    )
    by_state = {
        state: {
            "transition_probability": _float_value(
                values.get("transition_probability")
            ),
            "transition_penalty": _float_value(values.get("transition_penalty")),
            "weighted_transition_penalty": _float_value(values.get("state_probability"))
            * _float_value(values.get("transition_penalty")),
        }
        for state, values in sorted(alpha_by_state.items())
    }
    return {
        "transition_cost_unit": transition_cost_unit,
        "weighted_transition_penalty": weighted_transition_penalty,
        "penalty_share_of_abs_expectancy": (
            weighted_transition_penalty / weighted_raw_abs_expectancy
            if weighted_raw_abs_expectancy
            else 0.0
        ),
        "transition_costs_material": weighted_transition_penalty > 0.0,
        "per_state": by_state,
    }


def _stability_contribution(
    alpha_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, float | bool]:
    stabilities = tuple(
        _float_value(values.get("bounded_stability_score"))
        for values in alpha_by_state.values()
    )
    alphas = tuple(
        _float_value(values.get("stability_weighted_alpha"))
        for values in alpha_by_state.values()
    )
    alpha_magnitudes = tuple(abs(alpha) for alpha in alphas)
    signed_correlation = _correlation(stabilities, alphas)
    magnitude_correlation = _correlation(stabilities, alpha_magnitudes)
    return {
        "stability_to_signed_alpha_correlation": signed_correlation,
        "stability_to_alpha_magnitude_correlation": magnitude_correlation,
        "stability_is_not_profitability": abs(signed_correlation) < 0.95,
        "mean_bounded_stability_score": _mean(stabilities),
    }


def _comparison_vs_naive(
    alpha_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, float | bool]:
    naive_alpha = sum(
        _float_value(values.get("state_probability"))
        * _float_value(values.get("regime_conditional_edge"))
        for values in alpha_by_state.values()
    )
    regime_aware = sum(
        _float_value(values.get("state_probability"))
        * _float_value(values.get("transition_adjusted_expectancy"))
        for values in alpha_by_state.values()
    )
    stability_weighted = sum(
        _float_value(values.get("system_alpha_contribution"))
        for values in alpha_by_state.values()
    )
    return {
        "naive_conditional_expectancy": naive_alpha,
        "regime_aware_transition_adjusted_expectancy": regime_aware,
        "stability_weighted_system_alpha": stability_weighted,
        "regime_aware_delta_vs_naive": regime_aware - naive_alpha,
        "stability_weighted_delta_vs_naive": stability_weighted - naive_alpha,
        "system_alpha_differs_from_naive": abs(stability_weighted - naive_alpha)
        > 1e-12,
    }


def _regime_exposure_contribution(
    alpha_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    by_state = {
        state: {
            "exposure_share": _float_value(values.get("exposure_share")),
            "regime_exposure_contribution": _float_value(
                values.get("regime_exposure_contribution")
            ),
        }
        for state, values in sorted(alpha_by_state.items())
    }
    return {
        "per_state": by_state,
        "total_exposure_weighted_alpha": sum(
            _float_value(values.get("regime_exposure_contribution"))
            for values in alpha_by_state.values()
        ),
    }


def _artifact_consistency(
    *,
    labels: Sequence[dict[str, object]],
    state_space: Sequence[str],
    transition_model: Mapping[str, object],
    stability_model: Mapping[str, object],
    forecastability: Mapping[str, object],
    decision_overlay: Mapping[str, object],
) -> dict[str, bool]:
    overlay_consistency = _mapping(decision_overlay.get("artifact_consistency"))
    return {
        "state_rows_match_stability": len(labels)
        == int(_float_value(stability_model.get("state_label_rows"))),
        "unique_states_match_transition": len(state_space)
        == int(_float_value(transition_model.get("unique_states"))),
        "unique_states_match_forecastability": len(state_space)
        == int(_float_value(forecastability.get("unique_states"))),
        "overlay_artifacts_consistent": all(
            bool(overlay_consistency.get(key))
            for key in (
                "state_rows_match_stability",
                "unique_states_match_transition",
                "unique_states_match_forecastability",
            )
        ),
    }


def _state_counts(labels: Sequence[dict[str, object]]) -> Counter[str]:
    return Counter(_state_key(label) for label in labels)


def _state_stability_score(
    stability_model: Mapping[str, object],
    state: str,
) -> float:
    stability_metrics = _mapping(stability_model.get("stability_entropy_metrics"))
    per_state = _mapping(stability_metrics.get("per_state"))
    metrics = _mapping(per_state.get(state))
    return _float_value(metrics.get("stability_score"))


def _bounded_stability_score(value: float) -> float:
    if value <= 0.0:
        return 0.0
    return value / (1.0 + value)


def _state_exposure(
    decision_overlay: Mapping[str, object],
    state: str,
) -> Mapping[str, object]:
    return _mapping(
        _mapping(decision_overlay.get("trade_concentration_by_regime")).get(state)
    )


def _transition_cost_unit(decision_overlay: Mapping[str, object]) -> float:
    comparison = _mapping(decision_overlay.get("baseline_vs_overlay_comparison"))
    drawdown_reduction = abs(_float_value(comparison.get("drawdown_reduction")))
    symbols = max(int(_float_value(decision_overlay.get("symbols"))), 1)
    return drawdown_reduction / symbols


def _state_key(label_or_state: Mapping[str, object]) -> str:
    if "state" in label_or_state and isinstance(label_or_state["state"], dict):
        state = _mapping(label_or_state["state"])
    else:
        state = label_or_state
    return "_".join(
        str(state.get(key, "UNKNOWN")) for key in ("volatility", "trend", "stress")
    )


def _state_parts(state: str) -> dict[str, str]:
    parts = state.split("_")
    return {
        "volatility": parts[0] if len(parts) > 0 else "UNKNOWN",
        "trend": parts[1] if len(parts) > 1 else "UNKNOWN",
        "stress": parts[2] if len(parts) > 2 else "UNKNOWN",
    }


def _alpha_sign(value: float) -> str:
    if value > 0.0:
        return "positive"
    if value < 0.0:
        return "negative"
    return "neutral"


def _load_json_object(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Regime-to-alpha translation requires JSON object artifacts")
    return payload


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_mean = _mean(left)
    right_mean = _mean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_denominator = sum((value - left_mean) ** 2 for value in left) ** 0.5
    right_denominator = sum((value - right_mean) ** 2 for value in right) ** 0.5
    if left_denominator == 0.0 or right_denominator == 0.0:
        return 0.0
    return numerator / (left_denominator * right_denominator)


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
