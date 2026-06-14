import json
from pathlib import Path

from scripts.behavior_validation.execution_reality_model_v1 import (
    SUMMARY_FILENAME,
    build_execution_reality_report,
    run_execution_reality_model,
)

FORBIDDEN_SOURCE_TOKENS = (
    "from scripts.behavior_validation.feature_transform",
    "from scripts.behavior_validation.signal",
    "from scripts.behavior_validation.decision",
    "from scripts.behavior_validation.evaluation_runner",
    "from scripts.behavior_validation.economic_closure",
    "optimize",
    "fit(",
    "predict(",
)


def test_execution_reality_model_is_deterministic():
    inputs = _inputs()

    first = build_execution_reality_report(regime_alpha=inputs)
    second = build_execution_reality_report(regime_alpha=inputs)

    assert first == second
    assert (
        first["execution_adjusted_system_alpha"]["alpha_decreased_after_costs"] is True
    )


def test_execution_reality_model_has_no_forbidden_dependencies_or_changes():
    source = Path(
        "backend/scripts/behavior_validation/execution_reality_model_v1.py"
    ).read_text(encoding="utf-8")
    report = build_execution_reality_report(regime_alpha=_inputs())

    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source
    assert report["source_constraints"]["new_data_used"] is False
    assert report["source_constraints"]["new_features_created"] is False
    assert report["source_constraints"]["signals_modified"] is False
    assert report["source_constraints"]["decision_logic_modified"] is False
    assert report["source_constraints"]["regime_models_modified"] is False
    assert report["source_constraints"]["learning_model_used"] is False
    assert report["source_constraints"]["optimization_used"] is False


def test_execution_reality_model_costs_reduce_alpha_but_keep_structure():
    report = build_execution_reality_report(regime_alpha=_inputs())
    system = report["execution_adjusted_system_alpha"]

    assert system["execution_adjusted_system_alpha"] < system["raw_system_alpha"]
    assert system["some_regimes_become_unprofitable"] is True
    assert system["some_regimes_remain_positive"] is True
    assert system["structured_after_execution"] is True


def test_execution_reality_model_reports_cost_and_fragility_metrics():
    report = build_execution_reality_report(regime_alpha=_inputs())

    cost = report["slippage_cost_decomposition"]["system"]
    ranking = report["regime_fragility_ranking"]
    assert cost["fee_cost"] > 0.0
    assert cost["slippage_cost"] > cost["fee_cost"]
    assert cost["transition_impact"] > 0.0
    assert (
        ranking[0]["regime_fragility_factor"] >= ranking[-1]["regime_fragility_factor"]
    )


def test_execution_reality_model_writes_required_artifact(tmp_path):
    source_path = tmp_path / "regime_to_alpha_v1.json"
    source_path.write_text(json.dumps(_inputs()), encoding="utf-8")

    report = run_execution_reality_model(source_path, output_dir=tmp_path)

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["input_rows"] == 100
    assert (
        report["artifact_consistency"]["regime_alpha_has_mixed_contributions"] is True
    )
    assert report["oos_robustness_proxy"]["noise_injection_is_deterministic"] is True


def _inputs() -> dict[str, object]:
    alpha_per_state = {
        "LOW_UP_STABLE": {
            "stability_weighted_alpha": 0.4,
            "state_probability": 0.45,
            "mean_abs_exposure": 0.2,
            "transition_probability": 0.1,
            "transition_penalty": 0.003,
            "stay_probability": 0.9,
        },
        "HIGH_UP_TRANSITIONAL": {
            "stability_weighted_alpha": 0.045,
            "state_probability": 0.1,
            "mean_abs_exposure": 0.3,
            "transition_probability": 0.7,
            "transition_penalty": 0.012,
            "stay_probability": 0.3,
        },
        "HIGH_DOWN_CHAOTIC": {
            "stability_weighted_alpha": -0.15,
            "state_probability": 0.25,
            "mean_abs_exposure": 0.25,
            "transition_probability": 0.6,
            "transition_penalty": 0.01,
            "stay_probability": 0.4,
        },
        "MID_FLAT_TRANSITIONAL": {
            "stability_weighted_alpha": 0.0,
            "state_probability": 0.2,
            "mean_abs_exposure": 0.15,
            "transition_probability": 0.5,
            "transition_penalty": 0.008,
            "stay_probability": 0.5,
        },
    }
    return {
        "input_rows": 100,
        "unique_states": len(alpha_per_state),
        "final_system_alpha_score": 0.147,
        "alpha_per_state": alpha_per_state,
        "weighted_system_alpha": {
            "has_positive_and_negative_regimes": True,
        },
        "comparison_vs_naive_baseline": {
            "system_alpha_differs_from_naive": True,
        },
        "source_constraints": {
            "new_data_used": False,
            "new_features_created": False,
            "learning_model_used": False,
        },
    }
