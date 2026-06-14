import json
from pathlib import Path

from scripts.behavior_validation.oos_survivor_validation_v1 import (
    SUMMARY_FILENAME,
    build_oos_survivor_validation_report,
    run_oos_survivor_validation,
)

FORBIDDEN_SOURCE_TOKENS = (
    "import random",
    ".shuffle(",
    "fit(",
    "predict(",
    "GridSearch",
    "from scripts.behavior_validation.feature_transform",
    "from scripts.behavior_validation.evaluation_runner",
    "from scripts.behavior_validation.execution_reality_model_v1 import",
    "from scripts.behavior_validation.regime_survival_optimization_v1 import",
)


def test_oos_survivor_validation_is_deterministic():
    inputs = _inputs()

    first = build_oos_survivor_validation_report(**inputs)
    second = build_oos_survivor_validation_report(**inputs)

    assert first == second
    assert first["split"]["method"] == "chronological_unique_timestamp_split"
    assert first["survivor_count"] == 2


def test_oos_survivor_validation_uses_train_survivors_without_test_leakage():
    report = build_oos_survivor_validation_report(**_inputs())

    assert report["train_phase"]["survivor_regimes"] == (
        "LOW_UP_STABLE",
        "MID_UP_STABLE",
    )
    assert report["test_phase"]["retained_survivor_regimes"] == (
        "LOW_UP_STABLE",
        "MID_UP_STABLE",
    )
    assert (
        report["source_constraints"]["test_data_used_for_survivor_selection"] is False
    )
    assert report["survivor_retention"]["retention_ratio"] == 1.0


def test_oos_survivor_validation_reports_alpha_retention_and_verdict():
    report = build_oos_survivor_validation_report(**_inputs())

    assert report["train_alpha"] > 0.0
    assert report["test_alpha"] > 0.0
    assert report["alpha_retention"] >= 0.5
    assert report["verdict"] == "ROBUST_EDGE"
    assert report["survivor_alpha"]["delta"] < 0.0


def test_oos_survivor_validation_reports_frequency_and_composition_drift():
    report = build_oos_survivor_validation_report(**_inputs())
    drift = report["frequency_drift"]
    composition = report["regime_composition_drift"]

    assert (
        drift["LOW_UP_STABLE"]["train_frequency"]
        > drift["LOW_UP_STABLE"]["test_frequency"]
    )
    assert drift["MID_UP_STABLE"]["appears_in_test"] is True
    assert composition["absolute_probability_mass_change"] > 0.0
    assert "probability_mass_delta" in composition


def test_oos_survivor_validation_has_no_forbidden_model_changes():
    source = Path(
        "backend/scripts/behavior_validation/oos_survivor_validation_v1.py"
    ).read_text(encoding="utf-8")
    report = build_oos_survivor_validation_report(**_inputs())

    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source
    assert report["source_constraints"]["features_modified"] is False
    assert report["source_constraints"]["states_modified"] is False
    assert report["source_constraints"]["transitions_modified"] is False
    assert report["source_constraints"]["stability_model_modified"] is False
    assert report["source_constraints"]["alpha_model_modified"] is False
    assert report["source_constraints"]["execution_model_modified"] is False
    assert report["source_constraints"]["survivor_selection_logic_modified"] is False
    assert report["source_constraints"]["learning_model_used"] is False
    assert report["source_constraints"]["optimization_used"] is False
    assert report["source_constraints"]["parameter_search_used"] is False
    assert report["source_constraints"]["tuning_used"] is False


def test_oos_survivor_validation_writes_required_artifact(tmp_path):
    inputs = _inputs()
    labels_path = tmp_path / "market_state_labeling_v1.json"
    dataset_dir = tmp_path / "expanded_dataset_v1"
    alpha_path = tmp_path / "regime_to_alpha_v1.json"
    execution_path = tmp_path / "execution_reality_model_v1.json"
    survivor_path = tmp_path / "regime_survival_optimization_v1.json"
    labels_path.write_text(
        json.dumps({"state_labels": inputs["labels"]}),
        encoding="utf-8",
    )
    dataset_dir.mkdir()
    for symbol in ("BTCUSDT", "ETHUSDT"):
        (dataset_dir / f"{symbol}_candles.csv").write_text(
            "timestamp,symbol,open,high,low,close,volume,simulation_status\n"
            + "\n".join(
                f"2024-01-01T0{index}:00:00Z,{symbol},1,1,1,1,1,accepted"
                for index in range(5)
            )
            + "\n",
            encoding="utf-8",
        )
    alpha_path.write_text(json.dumps(inputs["regime_alpha"]), encoding="utf-8")
    execution_path.write_text(json.dumps(inputs["execution_reality"]), encoding="utf-8")
    survivor_path.write_text(
        json.dumps(inputs["survivor_optimization"]),
        encoding="utf-8",
    )

    report = run_oos_survivor_validation(
        state_labels_path=labels_path,
        dataset_dir=dataset_dir,
        regime_alpha_path=alpha_path,
        execution_reality_path=execution_path,
        survivor_optimization_path=survivor_path,
        output_dir=tmp_path,
    )

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["input_rows"] == 10
    assert report["artifact_consistency"]["labels_match_dataset_rows"] is True


def _inputs() -> dict[str, object]:
    labels = _labels()
    return {
        "labels": labels,
        "dataset_summary": {
            "rows": len(labels),
            "symbols": ("BTCUSDT", "ETHUSDT"),
            "path": "test",
        },
        "regime_alpha": {"input_rows": len(labels)},
        "execution_reality": {
            "effective_alpha_per_regime": {
                "LOW_UP_STABLE": {
                    "raw_alpha": 0.20,
                    "executable_alpha": 0.10,
                },
                "MID_UP_STABLE": {
                    "raw_alpha": 0.16,
                    "executable_alpha": 0.08,
                },
                "HIGH_DOWN_CHAOTIC": {
                    "raw_alpha": -0.30,
                    "executable_alpha": -0.20,
                },
            }
        },
        "survivor_optimization": {
            "input_rows": len(labels),
            "unique_states": 3,
            "survival_threshold": 0.0,
            "survival_score_per_regime": {
                "LOW_UP_STABLE": {"is_viable": True, "survival_score": 0.10},
                "MID_UP_STABLE": {"is_viable": True, "survival_score": 0.06},
                "HIGH_DOWN_CHAOTIC": {"is_viable": False, "survival_score": 0.0},
            },
        },
    }


def _labels() -> list[dict[str, object]]:
    states_by_timestamp = {
        "2024-01-01T00:00:00Z": ("LOW_UP_STABLE", "MID_UP_STABLE"),
        "2024-01-01T01:00:00Z": ("LOW_UP_STABLE", "LOW_UP_STABLE"),
        "2024-01-01T02:00:00Z": ("MID_UP_STABLE", "LOW_UP_STABLE"),
        "2024-01-01T03:00:00Z": ("LOW_UP_STABLE", "MID_UP_STABLE"),
        "2024-01-01T04:00:00Z": ("MID_UP_STABLE", "HIGH_DOWN_CHAOTIC"),
    }
    labels: list[dict[str, object]] = []
    for timestamp, states in states_by_timestamp.items():
        for symbol, state in zip(("BTCUSDT", "ETHUSDT"), states, strict=True):
            labels.append(
                {
                    "event_id": f"{symbol}-{timestamp}",
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "state": _state_object(state),
                }
            )
    return labels


def _state_object(state_key: str) -> dict[str, str]:
    volatility, trend, stress = state_key.split("_")
    return {"volatility": volatility, "trend": trend, "stress": stress}
