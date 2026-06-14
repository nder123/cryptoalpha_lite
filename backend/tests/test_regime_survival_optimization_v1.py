import json
from pathlib import Path

from scripts.behavior_validation.regime_survival_optimization_v1 import (
    SUMMARY_FILENAME,
    build_regime_survival_report,
    run_regime_survival_optimization,
)

FORBIDDEN_SOURCE_TOKENS = (
    "from scripts.behavior_validation.feature_transform",
    "from scripts.behavior_validation.evaluation_runner",
    "from scripts.behavior_validation.economic_closure",
    "from scripts.behavior_validation.execution_reality_model_v1 import",
    "fit(",
    "predict(",
)


def test_regime_survival_optimization_is_deterministic():
    inputs = _inputs()

    first = build_regime_survival_report(**inputs)
    second = build_regime_survival_report(**inputs)

    assert first == second
    assert first["filtered_regime_set"]["viable_regime_count"] == 2


def test_regime_survival_optimization_has_no_forbidden_changes():
    source = Path(
        "backend/scripts/behavior_validation/regime_survival_optimization_v1.py"
    ).read_text(encoding="utf-8")
    report = build_regime_survival_report(**_inputs())

    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source
    assert report["source_constraints"]["new_data_used"] is False
    assert report["source_constraints"]["new_features_created"] is False
    assert report["source_constraints"]["pipeline_modified"] is False
    assert report["source_constraints"]["regime_labeling_modified"] is False
    assert report["source_constraints"]["execution_model_modified"] is False
    assert report["source_constraints"]["learning_model_used"] is False
    assert report["source_constraints"]["optimization_loop_used"] is False


def test_regime_survival_optimization_filters_collapses_and_improves_alpha():
    report = build_regime_survival_report(**_inputs())

    assert report["collapse_elimination_report"]["collapse_zones_removed"] is True
    assert "HIGH_DOWN_STABLE" in report["filtered_regime_set"]["eliminated_regimes"]
    assert report["pre_post_alpha_comparison"]["post_filter_alpha_positive"] is True
    assert report["pre_post_alpha_comparison"]["post_minus_pre_alpha"] > 0.0
    assert (
        report["pre_post_alpha_comparison"][
            "surviving_regimes_have_positive_expectancy"
        ]
        is True
    )


def test_regime_survival_optimization_reports_concentration_and_correlation():
    report = build_regime_survival_report(**_inputs())
    concentration = report["survivor_concentration_metrics"]

    assert concentration["pruned_regime_count"] == 3
    assert concentration["significant_regime_pruning"] is True
    assert concentration["positive_alpha_retained_share"] == 1.0
    assert "correlation" in report["survival_vs_stability_correlation"]
    assert report["survival_vs_stability_correlation"]["stable_is_not_survivor"] is True


def test_regime_survival_optimization_writes_required_artifact(tmp_path):
    inputs = _inputs()
    stability_path = tmp_path / "state_stability_model_v1.json"
    alpha_path = tmp_path / "regime_to_alpha_v1.json"
    execution_path = tmp_path / "execution_reality_model_v1.json"
    stability_path.write_text(json.dumps(inputs["stability_model"]), encoding="utf-8")
    alpha_path.write_text(json.dumps(inputs["regime_alpha"]), encoding="utf-8")
    execution_path.write_text(json.dumps(inputs["execution_reality"]), encoding="utf-8")

    report = run_regime_survival_optimization(
        stability_model_path=stability_path,
        regime_alpha_path=alpha_path,
        execution_reality_path=execution_path,
        output_dir=tmp_path,
    )

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["input_rows"] == 100
    assert (
        report["artifact_consistency"]["execution_alpha_decreased_after_costs"] is True
    )


def _inputs() -> dict[str, object]:
    states = {
        "LOW_UP_STABLE": {
            "stability": 1.5,
            "probability": 0.35,
            "executable": 0.22,
            "raw": 0.3,
            "fragility": 0.15,
            "collapsed": False,
            "slippage": 0.002,
            "transition": 0.002,
        },
        "HIGH_UP_TRANSITIONAL": {
            "stability": 0.7,
            "probability": 0.15,
            "executable": 0.08,
            "raw": 0.15,
            "fragility": 0.45,
            "collapsed": False,
            "slippage": 0.008,
            "transition": 0.006,
        },
        "HIGH_DOWN_STABLE": {
            "stability": 2.0,
            "probability": 0.05,
            "executable": -0.01,
            "raw": 0.05,
            "fragility": 0.9,
            "collapsed": True,
            "slippage": 0.01,
            "transition": 0.02,
        },
        "HIGH_DOWN_CHAOTIC": {
            "stability": 0.8,
            "probability": 0.25,
            "executable": -0.2,
            "raw": -0.25,
            "fragility": 0.55,
            "collapsed": False,
            "slippage": 0.01,
            "transition": 0.01,
        },
        "MID_FLAT_TRANSITIONAL": {
            "stability": 0.6,
            "probability": 0.2,
            "executable": -0.02,
            "raw": 0.0,
            "fragility": 0.5,
            "collapsed": False,
            "slippage": 0.006,
            "transition": 0.006,
        },
    }
    return {
        "stability_model": {
            "unique_states": len(states),
            "stability_entropy_metrics": {
                "per_state": {
                    state: {"stability_score": values["stability"]}
                    for state, values in states.items()
                }
            },
        },
        "regime_alpha": {
            "input_rows": 100,
            "unique_states": len(states),
            "source_constraints": {
                "new_data_used": False,
                "new_features_created": False,
                "learning_model_used": False,
            },
            "alpha_per_state": {
                state: {"state_probability": values["probability"]}
                for state, values in states.items()
            },
        },
        "execution_reality": {
            "source_constraints": {
                "new_data_used": False,
                "new_features_created": False,
                "learning_model_used": False,
            },
            "raw_alpha_vs_executable_alpha": {
                "alpha_decreased_after_costs": True,
            },
            "execution_adjusted_system_alpha": {
                "execution_adjusted_system_alpha": -0.01,
            },
            "effective_alpha_per_regime": {
                state: {
                    "executable_alpha": values["executable"],
                    "raw_alpha": values["raw"],
                    "state_probability": values["probability"],
                    "regime_fragility_factor": values["fragility"],
                    "alpha_collapsed": values["collapsed"],
                    "slippage_cost": values["slippage"],
                    "transition_impact": values["transition"],
                }
                for state, values in states.items()
            },
        },
    }
