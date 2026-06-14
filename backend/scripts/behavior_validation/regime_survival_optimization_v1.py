from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

SUMMARY_FILENAME = "regime_survival_optimization_v1.json"
DEFAULT_STABILITY_MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "state_stability_model_v1.json"
)
DEFAULT_REGIME_ALPHA_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "regime_to_alpha_v1.json"
)
DEFAULT_EXECUTION_REALITY_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "execution_reality_model_v1.json"
)
SURVIVAL_THRESHOLD = 0.0


def run_regime_survival_optimization(
    *,
    stability_model_path: Path | str = DEFAULT_STABILITY_MODEL_PATH,
    regime_alpha_path: Path | str = DEFAULT_REGIME_ALPHA_PATH,
    execution_reality_path: Path | str = DEFAULT_EXECUTION_REALITY_PATH,
    output_dir: Path | None = None,
) -> dict[str, object]:
    stability_model = _load_json_object(stability_model_path)
    regime_alpha = _load_json_object(regime_alpha_path)
    execution_reality = _load_json_object(execution_reality_path)
    report = build_regime_survival_report(
        stability_model=stability_model,
        regime_alpha=regime_alpha,
        execution_reality=execution_reality,
    )
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_regime_survival_report(
    *,
    stability_model: Mapping[str, object],
    regime_alpha: Mapping[str, object],
    execution_reality: Mapping[str, object],
) -> dict[str, object]:
    alpha_by_state = _mapping(regime_alpha.get("alpha_per_state"))
    execution_by_state = _mapping(execution_reality.get("effective_alpha_per_regime"))
    survival_by_state = {
        state: _state_survival(
            state=state,
            alpha_metrics=_mapping(alpha_metrics),
            execution_metrics=_mapping(execution_by_state.get(state)),
            stability_model=stability_model,
        )
        for state, alpha_metrics in alpha_by_state.items()
    }
    viable_regimes = tuple(
        state
        for state, metrics in sorted(survival_by_state.items())
        if bool(metrics["is_viable"])
    )
    return {
        "input_rows": int(_float_value(regime_alpha.get("input_rows"))),
        "unique_states": int(_float_value(regime_alpha.get("unique_states"))),
        "survival_threshold": SURVIVAL_THRESHOLD,
        "survival_score_per_regime": dict(sorted(survival_by_state.items())),
        "filtered_regime_set": {
            "viable_regimes": viable_regimes,
            "viable_regime_count": len(viable_regimes),
            "eliminated_regimes": tuple(
                state
                for state, metrics in sorted(survival_by_state.items())
                if not bool(metrics["is_viable"])
            ),
            "eliminated_regime_count": len(survival_by_state) - len(viable_regimes),
        },
        "pre_post_alpha_comparison": _pre_post_alpha_comparison(
            survival_by_state,
            execution_reality,
        ),
        "collapse_elimination_report": _collapse_elimination_report(survival_by_state),
        "survivor_concentration_metrics": _survivor_concentration_metrics(
            survival_by_state
        ),
        "survival_vs_stability_correlation": _survival_vs_stability(survival_by_state),
        "execution_adjusted_ranking": _execution_adjusted_ranking(survival_by_state),
        "final_survivor_system_alpha": _survivor_system_alpha(survival_by_state)[
            "survivor_system_alpha"
        ],
        "artifact_consistency": _artifact_consistency(
            stability_model=stability_model,
            regime_alpha=regime_alpha,
            execution_reality=execution_reality,
            survival_by_state=survival_by_state,
        ),
        "source_constraints": {
            "input_layers": (
                "state_stability_model_v1",
                "regime_to_alpha_v1",
                "execution_reality_model_v1",
            ),
            "new_data_used": False,
            "new_features_created": False,
            "pipeline_modified": False,
            "regime_labeling_modified": False,
            "execution_model_modified": False,
            "learning_model_used": False,
            "optimization_loop_used": False,
            "adaptive_learning_used": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run regime survival optimization v1")
    parser.add_argument(
        "--stability-model",
        type=Path,
        default=DEFAULT_STABILITY_MODEL_PATH,
    )
    parser.add_argument(
        "--regime-alpha",
        type=Path,
        default=DEFAULT_REGIME_ALPHA_PATH,
    )
    parser.add_argument(
        "--execution-reality",
        type=Path,
        default=DEFAULT_EXECUTION_REALITY_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_regime_survival_optimization(
        stability_model_path=args.stability_model,
        regime_alpha_path=args.regime_alpha,
        execution_reality_path=args.execution_reality,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _state_survival(
    *,
    state: str,
    alpha_metrics: Mapping[str, object],
    execution_metrics: Mapping[str, object],
    stability_model: Mapping[str, object],
) -> dict[str, float | bool | str]:
    executable_alpha = _float_value(execution_metrics.get("executable_alpha"))
    raw_alpha = _float_value(execution_metrics.get("raw_alpha"))
    state_probability = _float_value(alpha_metrics.get("state_probability"))
    bounded_stability = _bounded_stability_score(
        _state_stability_score(stability_model, state)
    )
    collapsed = bool(execution_metrics.get("alpha_collapsed"))
    fragility = _float_value(execution_metrics.get("regime_fragility_factor"))
    collapse_rate = 1.0 if collapsed else _clamp(fragility, 0.0, 1.0)
    survival_score = (
        max(0.0, executable_alpha) * bounded_stability * (1.0 - collapse_rate)
    )
    execution_penalty = _float_value(
        execution_metrics.get("slippage_cost")
    ) + _float_value(execution_metrics.get("transition_impact"))
    rank_score = survival_score - execution_penalty
    return {
        "state": state,
        "raw_alpha": raw_alpha,
        "executable_alpha": executable_alpha,
        "state_probability": state_probability,
        "bounded_stability_score": bounded_stability,
        "collapse_rate": collapse_rate,
        "alpha_collapsed": collapsed,
        "slippage_cost": _float_value(execution_metrics.get("slippage_cost")),
        "transition_impact": _float_value(execution_metrics.get("transition_impact")),
        "execution_penalty_for_rank": execution_penalty,
        "survival_score": survival_score,
        "execution_adjusted_rank_score": rank_score,
        "is_viable": survival_score > SURVIVAL_THRESHOLD,
        "weighted_executable_alpha": state_probability * executable_alpha,
        "weighted_survival_score": state_probability * survival_score,
    }


def _pre_post_alpha_comparison(
    survival_by_state: Mapping[str, Mapping[str, object]],
    execution_reality: Mapping[str, object],
) -> dict[str, float | bool]:
    system = _mapping(execution_reality.get("execution_adjusted_system_alpha"))
    pre_alpha = _float_value(system.get("execution_adjusted_system_alpha"))
    survivor_metrics = _survivor_system_alpha(survival_by_state)
    return {
        "pre_filter_execution_adjusted_alpha": pre_alpha,
        "post_filter_survivor_alpha": survivor_metrics["survivor_system_alpha"],
        "post_filter_normalized_survivor_alpha": survivor_metrics[
            "normalized_survivor_alpha"
        ],
        "post_minus_pre_alpha": survivor_metrics["survivor_system_alpha"] - pre_alpha,
        "survivor_probability_mass": survivor_metrics["survivor_probability_mass"],
        "post_filter_alpha_positive": survivor_metrics["survivor_system_alpha"] > 0.0,
        "surviving_regimes_have_positive_expectancy": all(
            _float_value(metrics.get("executable_alpha")) > 0.0
            for metrics in survival_by_state.values()
            if bool(metrics.get("is_viable"))
        ),
    }


def _collapse_elimination_report(
    survival_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    collapsed = tuple(
        state
        for state, metrics in sorted(survival_by_state.items())
        if bool(metrics.get("alpha_collapsed"))
    )
    eliminated = tuple(
        state
        for state, metrics in sorted(survival_by_state.items())
        if not bool(metrics.get("is_viable"))
    )
    return {
        "collapsed_regimes": collapsed,
        "collapsed_regime_count": len(collapsed),
        "eliminated_regimes": eliminated,
        "eliminated_regime_count": len(eliminated),
        "collapse_zones_removed": all(state in eliminated for state in collapsed),
    }


def _survivor_concentration_metrics(
    survival_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, float | int | bool]:
    total_count = len(survival_by_state)
    survivor_count = sum(
        1 for metrics in survival_by_state.values() if bool(metrics.get("is_viable"))
    )
    pre_positive_alpha = sum(
        max(_float_value(metrics.get("weighted_executable_alpha")), 0.0)
        for metrics in survival_by_state.values()
    )
    post_positive_alpha = sum(
        max(_float_value(metrics.get("weighted_executable_alpha")), 0.0)
        for metrics in survival_by_state.values()
        if bool(metrics.get("is_viable"))
    )
    pre_hhi = _herfindahl(
        tuple(
            max(_float_value(metrics.get("weighted_executable_alpha")), 0.0)
            for metrics in survival_by_state.values()
        )
    )
    pre_abs_hhi = _herfindahl(
        tuple(
            abs(_float_value(metrics.get("weighted_executable_alpha")))
            for metrics in survival_by_state.values()
        )
    )
    post_hhi = _herfindahl(
        tuple(
            max(_float_value(metrics.get("weighted_executable_alpha")), 0.0)
            for metrics in survival_by_state.values()
            if bool(metrics.get("is_viable"))
        )
    )
    return {
        "pre_filter_regime_count": total_count,
        "survivor_regime_count": survivor_count,
        "pruned_regime_count": total_count - survivor_count,
        "pruned_regime_share": (
            (total_count - survivor_count) / total_count if total_count else 0.0
        ),
        "positive_alpha_retained_share": (
            post_positive_alpha / pre_positive_alpha if pre_positive_alpha else 0.0
        ),
        "pre_filter_positive_alpha_hhi": pre_hhi,
        "pre_filter_abs_alpha_hhi": pre_abs_hhi,
        "post_filter_positive_alpha_hhi": post_hhi,
        "alpha_concentration_increased": post_hhi > pre_abs_hhi,
        "significant_regime_pruning": (total_count - survivor_count) >= total_count / 2,
    }


def _survival_vs_stability(
    survival_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, float | bool]:
    stability = tuple(
        _float_value(metrics.get("bounded_stability_score"))
        for metrics in survival_by_state.values()
    )
    survival = tuple(
        _float_value(metrics.get("survival_score"))
        for metrics in survival_by_state.values()
    )
    correlation = _correlation(stability, survival)
    return {
        "correlation": correlation,
        "stable_is_not_survivor": abs(correlation) < 0.95,
    }


def _execution_adjusted_ranking(
    survival_by_state: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, float | str | bool], ...]:
    ranking: tuple[dict[str, float | str | bool], ...] = tuple(
        {
            "state": state,
            "survival_score": _float_value(metrics.get("survival_score")),
            "execution_adjusted_rank_score": _float_value(
                metrics.get("execution_adjusted_rank_score")
            ),
            "is_viable": bool(metrics.get("is_viable")),
        }
        for state, metrics in survival_by_state.items()
    )
    return tuple(
        sorted(
            ranking,
            key=lambda item: (
                -_float_value(item.get("execution_adjusted_rank_score")),
                str(item.get("state")),
            ),
        )
    )


def _survivor_system_alpha(
    survival_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, float]:
    survivor_alpha = sum(
        _float_value(metrics.get("weighted_executable_alpha"))
        for metrics in survival_by_state.values()
        if bool(metrics.get("is_viable"))
    )
    survivor_mass = sum(
        _float_value(metrics.get("state_probability"))
        for metrics in survival_by_state.values()
        if bool(metrics.get("is_viable"))
    )
    return {
        "survivor_system_alpha": survivor_alpha,
        "survivor_probability_mass": survivor_mass,
        "normalized_survivor_alpha": (
            survivor_alpha / survivor_mass if survivor_mass else 0.0
        ),
    }


def _artifact_consistency(
    *,
    stability_model: Mapping[str, object],
    regime_alpha: Mapping[str, object],
    execution_reality: Mapping[str, object],
    survival_by_state: Mapping[str, Mapping[str, object]],
) -> dict[str, bool]:
    execution_constraints = _mapping(execution_reality.get("source_constraints"))
    alpha_constraints = _mapping(regime_alpha.get("source_constraints"))
    return {
        "state_count_matches_regime_alpha": len(survival_by_state)
        == int(_float_value(regime_alpha.get("unique_states"))),
        "state_count_matches_stability": len(survival_by_state)
        == int(_float_value(stability_model.get("unique_states"))),
        "execution_alpha_decreased_after_costs": bool(
            _mapping(execution_reality.get("raw_alpha_vs_executable_alpha")).get(
                "alpha_decreased_after_costs"
            )
        ),
        "source_used_no_new_data": alpha_constraints.get("new_data_used") is False
        and execution_constraints.get("new_data_used") is False,
        "source_used_no_new_features": alpha_constraints.get("new_features_created")
        is False
        and execution_constraints.get("new_features_created") is False,
        "source_used_no_learning": alpha_constraints.get("learning_model_used") is False
        and execution_constraints.get("learning_model_used") is False,
    }


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


def _herfindahl(values: Sequence[float]) -> float:
    total = sum(values)
    if total <= 0.0:
        return 0.0
    return sum((value / total) ** 2 for value in values if value > 0.0)


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


def _load_json_object(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Regime survival optimization requires JSON object artifacts")
    return payload


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
