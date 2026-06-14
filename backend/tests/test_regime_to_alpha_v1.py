import json
from pathlib import Path

from scripts.behavior_validation.regime_to_alpha_v1 import (
    SUMMARY_FILENAME,
    build_regime_to_alpha_report,
    run_regime_to_alpha_translation,
)

FORBIDDEN_SOURCE_TOKENS = (
    "from scripts.behavior_validation.evaluation_runner",
    "from scripts.behavior_validation.economic_closure",
    "from scripts.behavior_validation.feature_transform",
    "load_historical_data",
    "simulate_execution",
)


def test_regime_to_alpha_is_deterministic():
    inputs = _inputs()

    first = build_regime_to_alpha_report(**inputs)
    second = build_regime_to_alpha_report(**inputs)

    assert first == second
    assert first["weighted_system_alpha"]["has_positive_and_negative_regimes"] is True


def test_regime_to_alpha_has_no_pipeline_or_execution_dependency():
    source = Path(
        "backend/scripts/behavior_validation/regime_to_alpha_v1.py"
    ).read_text(encoding="utf-8")
    report = build_regime_to_alpha_report(**_inputs())

    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source
    assert report["source_constraints"]["new_data_used"] is False
    assert report["source_constraints"]["new_features_created"] is False
    assert report["source_constraints"]["execution_layer_modified"] is False
    assert report["source_constraints"]["evaluation_runner_modified"] is False
    assert report["source_constraints"]["economic_closure_modified"] is False
    assert report["source_constraints"]["learning_model_used"] is False
    assert report["source_constraints"]["optimization_used"] is False


def test_regime_to_alpha_decomposes_positive_negative_and_transition_costs():
    report = build_regime_to_alpha_report(**_inputs())

    assert report["alpha_per_state"]["LOW_UP_STABLE"]["alpha_sign"] == "positive"
    assert report["alpha_per_state"]["HIGH_DOWN_CHAOTIC"]["alpha_sign"] == "negative"
    assert report["transition_cost_breakdown"]["transition_costs_material"] is True
    assert report["transition_cost_breakdown"]["weighted_transition_penalty"] > 0.0
    assert (
        report["comparison_vs_naive_baseline"]["system_alpha_differs_from_naive"]
        is True
    )


def test_regime_to_alpha_reports_stability_and_exposure_contributions():
    report = build_regime_to_alpha_report(**_inputs())

    assert "stability_to_signed_alpha_correlation" in report["stability_contribution"]
    assert report["stability_contribution"]["stability_is_not_profitability"] is True
    assert (
        report["regime_exposure_contribution"]["total_exposure_weighted_alpha"] != 0.0
    )
    assert (
        report["final_system_alpha_score"]
        == report["weighted_system_alpha"]["stability_weighted_system_alpha"]
    )


def test_regime_to_alpha_writes_required_artifact(tmp_path):
    inputs = _inputs()
    label_path = tmp_path / "market_state_labeling_v1.json"
    transition_path = tmp_path / "state_transition_model_v1.json"
    stability_path = tmp_path / "state_stability_model_v1.json"
    forecastability_path = tmp_path / "regime_forecastability_v1.json"
    overlay_path = tmp_path / "regime_decision_overlay_v1.json"

    label_path.write_text(
        json.dumps({"state_labels": inputs["labels"]}),
        encoding="utf-8",
    )
    transition_path.write_text(
        json.dumps(inputs["transition_model"]),
        encoding="utf-8",
    )
    stability_path.write_text(
        json.dumps(inputs["stability_model"]),
        encoding="utf-8",
    )
    forecastability_path.write_text(
        json.dumps(inputs["forecastability"]),
        encoding="utf-8",
    )
    overlay_path.write_text(
        json.dumps(inputs["decision_overlay"]),
        encoding="utf-8",
    )

    report = run_regime_to_alpha_translation(
        label_path,
        transition_model_path=transition_path,
        stability_model_path=stability_path,
        forecastability_path=forecastability_path,
        decision_overlay_path=overlay_path,
        output_dir=tmp_path,
    )

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["input_rows"] == len(inputs["labels"])
    assert report["artifact_consistency"]["overlay_artifacts_consistent"] is True


def _inputs() -> dict[str, object]:
    labels = _labels()
    return {
        "labels": labels,
        "transition_model": {"unique_states": 3},
        "stability_model": {
            "state_label_rows": len(labels),
            "stability_entropy_metrics": {
                "per_state": {
                    "LOW_UP_STABLE": {"stability_score": 0.9},
                    "HIGH_DOWN_CHAOTIC": {"stability_score": 0.8},
                    "MID_FLAT_TRANSITIONAL": {"stability_score": 0.6},
                }
            },
        },
        "forecastability": {
            "unique_states": 3,
            "forecastability_score_per_state": {
                "LOW_UP_STABLE": {
                    "forecastability_score": 0.6,
                    "stay_probability": 0.7,
                    "one_step_transition_risk": 0.3,
                },
                "HIGH_DOWN_CHAOTIC": {
                    "forecastability_score": 0.55,
                    "stay_probability": 0.6,
                    "one_step_transition_risk": 0.4,
                },
                "MID_FLAT_TRANSITIONAL": {
                    "forecastability_score": 0.4,
                    "stay_probability": 0.5,
                    "one_step_transition_risk": 0.5,
                },
            },
        },
        "decision_overlay": {
            "symbols": 1,
            "baseline_vs_overlay_comparison": {"drawdown_reduction": 0.06},
            "artifact_consistency": {
                "state_rows_match_stability": True,
                "unique_states_match_transition": True,
                "unique_states_match_forecastability": True,
            },
            "trade_concentration_by_regime": {
                "LOW_UP_STABLE": {
                    "mean_abs_exposure": 0.2,
                    "share_of_abs_exposure": 0.5,
                },
                "HIGH_DOWN_CHAOTIC": {
                    "mean_abs_exposure": 0.3,
                    "share_of_abs_exposure": 0.3,
                },
                "MID_FLAT_TRANSITIONAL": {
                    "mean_abs_exposure": 0.1,
                    "share_of_abs_exposure": 0.2,
                },
            },
        },
    }


def _labels():
    states = (
        ("LOW", "UP", "STABLE"),
        ("LOW", "UP", "STABLE"),
        ("LOW", "UP", "STABLE"),
        ("HIGH", "DOWN", "CHAOTIC"),
        ("HIGH", "DOWN", "CHAOTIC"),
        ("MID", "FLAT", "TRANSITIONAL"),
    )
    return tuple(
        {
            "event_id": f"event-{index}",
            "symbol": "BTCUSDT",
            "timestamp": f"2024-01-01T0{index}:00:00Z",
            "state": {
                "volatility": volatility,
                "trend": trend,
                "stress": stress,
            },
        }
        for index, (volatility, trend, stress) in enumerate(states)
    )
