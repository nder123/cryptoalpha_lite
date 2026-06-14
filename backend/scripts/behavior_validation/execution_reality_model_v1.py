from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

SUMMARY_FILENAME = "execution_reality_model_v1.json"
DEFAULT_REGIME_ALPHA_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "regime_to_alpha_v1.json"
)
VOLATILITY_SLIPPAGE = {
    "LOW": 0.0015,
    "MID": 0.003,
    "HIGH": 0.006,
}
STRESS_SLIPPAGE_MULTIPLIER = {
    "STABLE": 0.75,
    "TRANSITIONAL": 1.25,
    "CHAOTIC": 1.7,
}
STRESS_FILL_BASE = {
    "STABLE": 0.93,
    "TRANSITIONAL": 0.78,
    "CHAOTIC": 0.64,
}
VOLATILITY_FILL_ADJUSTMENT = {
    "LOW": 0.04,
    "MID": 0.0,
    "HIGH": -0.06,
}
FEE_RATE = 0.001


def run_execution_reality_model(
    regime_alpha_path: Path | str = DEFAULT_REGIME_ALPHA_PATH,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    regime_alpha = _load_json_object(regime_alpha_path)
    report = build_execution_reality_report(regime_alpha=regime_alpha)
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_execution_reality_report(
    *,
    regime_alpha: Mapping[str, object],
) -> dict[str, object]:
    alpha_by_state = _mapping(regime_alpha.get("alpha_per_state"))
    max_state_probability = max(
        (
            _float_value(_mapping(values).get("state_probability"))
            for values in alpha_by_state.values()
        ),
        default=0.0,
    )
    effective_alpha = {
        state: _execution_adjusted_state_alpha(
            state=state,
            alpha_metrics=_mapping(metrics),
            max_state_probability=max_state_probability,
        )
        for state, metrics in alpha_by_state.items()
    }
    system = _system_execution_alpha(effective_alpha, regime_alpha)
    return {
        "input_rows": int(_float_value(regime_alpha.get("input_rows"))),
        "unique_states": int(_float_value(regime_alpha.get("unique_states"))),
        "effective_alpha_per_regime": dict(sorted(effective_alpha.items())),
        "raw_alpha_vs_executable_alpha": {
            "raw_system_alpha": system["raw_system_alpha"],
            "execution_adjusted_system_alpha": system[
                "execution_adjusted_system_alpha"
            ],
            "alpha_delta_after_execution": system["alpha_delta_after_execution"],
            "alpha_decreased_after_costs": system["alpha_decreased_after_costs"],
        },
        "slippage_cost_decomposition": _cost_breakdown(effective_alpha),
        "execution_adjusted_system_alpha": system,
        "regime_fragility_ranking": _fragility_ranking(effective_alpha),
        "alpha_survival_ratio": system["alpha_survival_ratio"],
        "oos_robustness_proxy": _oos_robustness_proxy(effective_alpha, regime_alpha),
        "artifact_consistency": _artifact_consistency(regime_alpha),
        "source_constraints": {
            "input_layers": ("regime_to_alpha_v1",),
            "new_data_used": False,
            "new_features_created": False,
            "signals_modified": False,
            "decision_logic_modified": False,
            "regime_models_modified": False,
            "learning_model_used": False,
            "optimization_used": False,
            "adaptive_tuning_used": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run execution reality model v1")
    parser.add_argument(
        "regime_alpha",
        nargs="?",
        type=Path,
        default=DEFAULT_REGIME_ALPHA_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_execution_reality_model(
        args.regime_alpha,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _execution_adjusted_state_alpha(
    *,
    state: str,
    alpha_metrics: Mapping[str, object],
    max_state_probability: float,
) -> dict[str, float | str | bool | int]:
    parts = _state_parts(state)
    raw_alpha = _float_value(alpha_metrics.get("stability_weighted_alpha"))
    state_probability = _float_value(alpha_metrics.get("state_probability"))
    mean_abs_exposure = _float_value(alpha_metrics.get("mean_abs_exposure"))
    transition_probability = _float_value(alpha_metrics.get("transition_probability"))
    transition_penalty = _float_value(alpha_metrics.get("transition_penalty"))
    liquidity_proxy = _liquidity_proxy(state_probability, max_state_probability)
    slippage = _slippage_cost(
        volatility=parts["volatility"],
        stress=parts["stress"],
        mean_abs_exposure=mean_abs_exposure,
        liquidity_proxy=liquidity_proxy,
    )
    fee = FEE_RATE * max(mean_abs_exposure, 0.0)
    transition_impact = transition_penalty * (1.0 + 2.25 * transition_probability)
    execution_penalty = fee + slippage + transition_impact
    fill_probability = _fill_probability(
        volatility=parts["volatility"],
        stress=parts["stress"],
        stay_probability=_float_value(alpha_metrics.get("stay_probability")),
        liquidity_proxy=liquidity_proxy,
    )
    fill_adjusted_alpha = raw_alpha * fill_probability
    executable_alpha = fill_adjusted_alpha - execution_penalty
    raw_positive = raw_alpha > 0.0
    collapsed = raw_positive and executable_alpha <= 0.0
    survival_ratio = (
        max(executable_alpha, 0.0) / raw_alpha if raw_positive and raw_alpha else 0.0
    )
    return {
        "state": state,
        "volatility_regime": parts["volatility"],
        "stress_regime": parts["stress"],
        "raw_alpha": raw_alpha,
        "fill_adjusted_alpha": fill_adjusted_alpha,
        "executable_alpha": executable_alpha,
        "effective_alpha": executable_alpha,
        "state_probability": state_probability,
        "liquidity_proxy": liquidity_proxy,
        "fill_probability": fill_probability,
        "fee_cost": fee,
        "slippage_cost": slippage,
        "transition_impact": transition_impact,
        "execution_penalty": execution_penalty,
        "alpha_survival_ratio": survival_ratio,
        "alpha_collapsed": collapsed,
        "regime_fragility_factor": _fragility_factor(
            stress=parts["stress"],
            transition_probability=transition_probability,
            fill_probability=fill_probability,
            liquidity_proxy=liquidity_proxy,
            collapsed=collapsed,
        ),
    }


def _system_execution_alpha(
    effective_alpha: Mapping[str, Mapping[str, object]],
    regime_alpha: Mapping[str, object],
) -> dict[str, float | bool]:
    raw_system_alpha = _float_value(regime_alpha.get("final_system_alpha_score"))
    execution_adjusted = sum(
        _float_value(values.get("state_probability"))
        * _float_value(values.get("executable_alpha"))
        for values in effective_alpha.values()
    )
    positive_effective = sum(
        _float_value(values.get("state_probability"))
        * _float_value(values.get("executable_alpha"))
        for values in effective_alpha.values()
        if _float_value(values.get("executable_alpha")) > 0.0
    )
    negative_effective = sum(
        _float_value(values.get("state_probability"))
        * _float_value(values.get("executable_alpha"))
        for values in effective_alpha.values()
        if _float_value(values.get("executable_alpha")) < 0.0
    )
    return {
        "raw_system_alpha": raw_system_alpha,
        "execution_adjusted_system_alpha": execution_adjusted,
        "alpha_delta_after_execution": execution_adjusted - raw_system_alpha,
        "alpha_survival_ratio": (
            execution_adjusted / raw_system_alpha if raw_system_alpha else 0.0
        ),
        "positive_executable_contribution": positive_effective,
        "negative_executable_contribution": negative_effective,
        "alpha_decreased_after_costs": execution_adjusted < raw_system_alpha,
        "some_regimes_remain_positive": positive_effective > 0.0,
        "some_regimes_become_unprofitable": any(
            bool(values.get("alpha_collapsed")) for values in effective_alpha.values()
        ),
        "structured_after_execution": positive_effective > 0.0
        and negative_effective < 0.0,
    }


def _cost_breakdown(
    effective_alpha: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    total_fee = _weighted_sum(effective_alpha, "fee_cost")
    total_slippage = _weighted_sum(effective_alpha, "slippage_cost")
    total_transition = _weighted_sum(effective_alpha, "transition_impact")
    return {
        "system": {
            "fee_cost": total_fee,
            "slippage_cost": total_slippage,
            "transition_impact": total_transition,
            "total_execution_penalty": total_fee + total_slippage + total_transition,
        },
        "per_regime": {
            state: {
                "fee_cost": _float_value(values.get("fee_cost")),
                "slippage_cost": _float_value(values.get("slippage_cost")),
                "transition_impact": _float_value(values.get("transition_impact")),
                "execution_penalty": _float_value(values.get("execution_penalty")),
            }
            for state, values in sorted(effective_alpha.items())
        },
    }


def _fragility_ranking(
    effective_alpha: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, float | str | bool], ...]:
    ranking: tuple[dict[str, float | str | bool], ...] = tuple(
        {
            "state": state,
            "regime_fragility_factor": _float_value(
                values.get("regime_fragility_factor")
            ),
            "raw_alpha": _float_value(values.get("raw_alpha")),
            "executable_alpha": _float_value(values.get("executable_alpha")),
            "alpha_collapsed": bool(values.get("alpha_collapsed")),
        }
        for state, values in effective_alpha.items()
    )
    return tuple(
        sorted(
            ranking,
            key=lambda item: (
                -_float_value(item.get("regime_fragility_factor")),
                str(item.get("state")),
            ),
        )
    )


def _oos_robustness_proxy(
    effective_alpha: Mapping[str, Mapping[str, object]],
    regime_alpha: Mapping[str, object],
) -> dict[str, object]:
    raw_system_alpha = _float_value(regime_alpha.get("final_system_alpha_score"))
    scenarios = {
        "base_execution": _scenario_system_alpha(
            effective_alpha,
            slippage_multiplier=1.0,
            fill_haircut=0.0,
        ),
        "mild_noise": _scenario_system_alpha(
            effective_alpha,
            slippage_multiplier=1.25,
            fill_haircut=0.04,
        ),
        "stress_noise": _scenario_system_alpha(
            effective_alpha,
            slippage_multiplier=1.5,
            fill_haircut=0.08,
        ),
    }
    worst_case = min(scenarios.values())
    return {
        "scenarios": scenarios,
        "worst_case_execution_alpha": worst_case,
        "worst_case_survival_ratio": (
            worst_case / raw_system_alpha if raw_system_alpha else 0.0
        ),
        "robustness_proxy_positive_under_base": scenarios["base_execution"] > 0.0,
        "robustness_proxy_positive_under_stress": scenarios["stress_noise"] > 0.0,
        "noise_injection_is_deterministic": True,
    }


def _scenario_system_alpha(
    effective_alpha: Mapping[str, Mapping[str, object]],
    *,
    slippage_multiplier: float,
    fill_haircut: float,
) -> float:
    total = 0.0
    for values in effective_alpha.values():
        raw_alpha = _float_value(values.get("raw_alpha"))
        state_probability = _float_value(values.get("state_probability"))
        fill_probability = max(
            _float_value(values.get("fill_probability")) - fill_haircut,
            0.0,
        )
        fee = _float_value(values.get("fee_cost"))
        slippage = _float_value(values.get("slippage_cost")) * slippage_multiplier
        transition = _float_value(values.get("transition_impact"))
        total += state_probability * (
            raw_alpha * fill_probability - fee - slippage - transition
        )
    return total


def _artifact_consistency(regime_alpha: Mapping[str, object]) -> dict[str, bool]:
    source_constraints = _mapping(regime_alpha.get("source_constraints"))
    weighted = _mapping(regime_alpha.get("weighted_system_alpha"))
    return {
        "regime_alpha_has_mixed_contributions": bool(
            weighted.get("has_positive_and_negative_regimes")
        ),
        "regime_alpha_differs_from_naive": bool(
            _mapping(regime_alpha.get("comparison_vs_naive_baseline")).get(
                "system_alpha_differs_from_naive"
            )
        ),
        "source_used_no_new_data": source_constraints.get("new_data_used") is False,
        "source_used_no_new_features": source_constraints.get("new_features_created")
        is False,
        "source_used_no_learning": source_constraints.get("learning_model_used")
        is False,
    }


def _slippage_cost(
    *,
    volatility: str,
    stress: str,
    mean_abs_exposure: float,
    liquidity_proxy: float,
) -> float:
    base = VOLATILITY_SLIPPAGE.get(volatility, VOLATILITY_SLIPPAGE["MID"])
    stress_multiplier = STRESS_SLIPPAGE_MULTIPLIER.get(
        stress,
        STRESS_SLIPPAGE_MULTIPLIER["TRANSITIONAL"],
    )
    liquidity_multiplier = 1.0 + (1.0 - liquidity_proxy) * 0.75
    exposure_multiplier = 1.0 + max(mean_abs_exposure, 0.0)
    return base * stress_multiplier * liquidity_multiplier * exposure_multiplier


def _fill_probability(
    *,
    volatility: str,
    stress: str,
    stay_probability: float,
    liquidity_proxy: float,
) -> float:
    fill = (
        STRESS_FILL_BASE.get(stress, STRESS_FILL_BASE["TRANSITIONAL"])
        + VOLATILITY_FILL_ADJUSTMENT.get(volatility, 0.0)
        + 0.08 * stay_probability
        + 0.04 * liquidity_proxy
    )
    return _clamp(fill, 0.25, 0.98)


def _fragility_factor(
    *,
    stress: str,
    transition_probability: float,
    fill_probability: float,
    liquidity_proxy: float,
    collapsed: bool,
) -> float:
    stress_component = {
        "STABLE": 0.15,
        "TRANSITIONAL": 0.55,
        "CHAOTIC": 0.8,
    }.get(stress, 0.5)
    collapse_component = 0.25 if collapsed else 0.0
    return _clamp(
        0.35 * stress_component
        + 0.35 * transition_probability
        + 0.2 * (1.0 - fill_probability)
        + 0.1 * (1.0 - liquidity_proxy)
        + collapse_component,
        0.0,
        1.0,
    )


def _weighted_sum(
    effective_alpha: Mapping[str, Mapping[str, object]],
    key: str,
) -> float:
    return sum(
        _float_value(values.get("state_probability")) * _float_value(values.get(key))
        for values in effective_alpha.values()
    )


def _liquidity_proxy(state_probability: float, max_state_probability: float) -> float:
    if max_state_probability <= 0.0:
        return 0.0
    return _clamp((state_probability / max_state_probability) ** 0.5, 0.05, 1.0)


def _state_parts(state: str) -> dict[str, str]:
    parts = state.split("_")
    return {
        "volatility": parts[0] if len(parts) > 0 else "UNKNOWN",
        "trend": parts[1] if len(parts) > 1 else "UNKNOWN",
        "stress": parts[2] if len(parts) > 2 else "UNKNOWN",
    }


def _load_json_object(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Execution reality model requires a JSON object artifact")
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
