import json
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.regime_decision_overlay_v1 import (
    SUMMARY_FILENAME,
    build_regime_decision_overlay_report,
    run_regime_decision_overlay,
)
from scripts.behavior_validation.regime_forecastability_v1 import (
    build_regime_forecastability_report,
)
from scripts.behavior_validation.state_stability_model_v1 import (
    build_state_stability_model,
)
from scripts.behavior_validation.state_transition_model_v1 import (
    build_state_transition_model,
)


def test_regime_decision_overlay_is_deterministic():
    data, labels, transition_model, stability_model, forecastability = _inputs()

    first = build_regime_decision_overlay_report(
        data=data,
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        forecastability=forecastability,
    )
    second = build_regime_decision_overlay_report(
        data=data,
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        forecastability=forecastability,
    )

    assert first == second
    assert first["validation"]["direction_changes"] == 0


def test_regime_decision_overlay_does_not_modify_restricted_layers():
    source = Path(
        "backend/scripts/behavior_validation/regime_decision_overlay_v1.py"
    ).read_text(encoding="utf-8")
    report = _report()

    assert "def _generate_decisions" not in source
    assert "feature_transform_microstructure" not in source
    assert report["validation"]["evaluation_engine_modified"] is False
    assert report["validation"]["economic_closure_modified"] is False
    assert report["validation"]["features_modified"] is False
    assert report["validation"]["ml_model_used"] is False
    assert report["validation"]["optimization_loop_used"] is False


def test_regime_decision_overlay_changes_exposure_by_regime():
    report = _report()
    stable = report["stability_improvement_metrics"]

    assert (
        report["baseline"]["regime_exposure_distribution"]
        != report["overlay"]["regime_exposure_distribution"]
    )
    assert stable["risk_reduced_in_chaotic_regimes"] is True
    assert stable["stable_regime_not_degraded"] is True
    assert (
        report["regime_weight_summary"]["weight_by_stress"]["CHAOTIC"]["mean_weight"]
        < report["regime_weight_summary"]["weight_by_stress"]["STABLE"]["mean_weight"]
    )


def test_regime_decision_overlay_reports_required_economic_and_risk_metrics():
    report = _report()

    assert "cost_adjusted_pnl_delta" in report["baseline_vs_overlay_comparison"]
    assert "risk_adjusted_pnl_delta" in report["baseline_vs_overlay_comparison"]
    assert "max_drawdown" in report["baseline"]
    assert "max_drawdown" in report["overlay"]
    assert report["artifact_consistency"]["forecastability_above_random"] is True
    assert (
        report["transition_sensitivity_improvement"][
            "unstable_transition_exposure_reduced"
        ]
        is True
    )


def test_regime_decision_overlay_writes_required_artifact(tmp_path):
    data, labels, transition_model, stability_model, forecastability = _inputs()
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    label_path = tmp_path / "market_state_labeling_v1.json"
    transition_path = tmp_path / "state_transition_model_v1.json"
    stability_path = tmp_path / "state_stability_model_v1.json"
    forecastability_path = tmp_path / "regime_forecastability_v1.json"

    _write_dataset(dataset_dir / "candles.csv", data)
    label_path.write_text(json.dumps({"state_labels": labels}), encoding="utf-8")
    transition_path.write_text(json.dumps(transition_model), encoding="utf-8")
    stability_path.write_text(json.dumps(stability_model), encoding="utf-8")
    forecastability_path.write_text(json.dumps(forecastability), encoding="utf-8")

    report = run_regime_decision_overlay(
        dataset_dir,
        state_labels_path=label_path,
        transition_model_path=transition_path,
        stability_model_path=stability_path,
        forecastability_path=forecastability_path,
        output_dir=tmp_path,
    )

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["dataset_rows"] == len(data)
    assert report["state_label_rows"] == len(labels)


def _report() -> dict[str, object]:
    data, labels, transition_model, stability_model, forecastability = _inputs()
    return build_regime_decision_overlay_report(
        data=data,
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        forecastability=forecastability,
    )


def _inputs():
    data = normalize_dataset(load_historical_data(_fixture_path()))
    labels = _labels()
    transition_model = build_state_transition_model(labels)
    stability_model = build_state_stability_model(
        labels=labels,
        transition_model=transition_model,
        dataset_rows=len(data),
    )
    forecastability = build_regime_forecastability_report(
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        dataset_rows=len(data),
    )
    return data, labels, transition_model, stability_model, forecastability


def _labels():
    states_by_symbol = {
        "BTCUSDT": (
            ("LOW", "UP", "STABLE"),
            ("LOW", "UP", "STABLE"),
            ("LOW", "UP", "STABLE"),
            ("HIGH", "DOWN", "CHAOTIC"),
            ("HIGH", "DOWN", "CHAOTIC"),
        ),
        "ETHUSDT": (
            ("LOW", "UP", "STABLE"),
            ("LOW", "UP", "STABLE"),
            ("MID", "FLAT", "TRANSITIONAL"),
            ("MID", "FLAT", "TRANSITIONAL"),
            ("HIGH", "DOWN", "CHAOTIC"),
        ),
    }
    return tuple(
        _label(symbol, index, state)
        for symbol, states in states_by_symbol.items()
        for index, state in enumerate(states)
    )


def _label(symbol: str, index: int, state: tuple[str, str, str]) -> dict[str, object]:
    return {
        "event_id": f"{symbol}-2026-01-01T00:0{index}:00Z",
        "symbol": symbol,
        "timestamp": f"2026-01-01T00:0{index}:00Z",
        "state": {
            "volatility": state[0],
            "trend": state[1],
            "stress": state[2],
        },
    }


def _fixture_path() -> Path:
    return Path("backend/tests/fixtures/behavior_validation")


def _write_dataset(path: Path, data: tuple[dict[str, object], ...]) -> None:
    rows = "\n".join(
        ",".join(
            (
                str(row["timestamp"]),
                str(row["symbol"]),
                str(row["open"]),
                str(row["high"]),
                str(row["low"]),
                str(row["close"]),
                str(row["volume"]),
                str(row["simulation_status"]),
            )
        )
        for row in data
    )
    path.write_text(
        "timestamp,symbol,open,high,low,close,volume,simulation_status\n" + rows + "\n",
        encoding="utf-8",
    )
