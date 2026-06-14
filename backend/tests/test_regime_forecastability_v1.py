import json
from pathlib import Path

from scripts.behavior_validation.regime_forecastability_v1 import (
    SUMMARY_FILENAME,
    build_regime_forecastability_report,
    run_regime_forecastability,
)
from scripts.behavior_validation.state_stability_model_v1 import (
    build_state_stability_model,
)
from scripts.behavior_validation.state_transition_model_v1 import (
    build_state_transition_model,
)

FORBIDDEN_SOURCE_TOKENS = ("evaluation_runner", "economic_closure")
FORBIDDEN_REPORT_TOKENS = ("decision", "pnl", "reward")


def test_regime_forecastability_is_deterministic_and_reproducible():
    labels = _labels()
    transition_model = build_state_transition_model(labels)
    stability_model = build_state_stability_model(
        labels=labels,
        transition_model=transition_model,
        dataset_rows=len(labels),
    )

    first = build_regime_forecastability_report(
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        dataset_rows=len(labels),
    )
    second = build_regime_forecastability_report(
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        dataset_rows=len(labels),
    )

    assert first == second
    assert first["global_forecastability_index"]["forecastability_above_random"] is True


def test_regime_forecastability_has_no_restricted_layer_leakage():
    source = Path(
        "backend/scripts/behavior_validation/regime_forecastability_v1.py"
    ).read_text(encoding="utf-8")
    report = _report()
    serialized = str(report).lower()

    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source
    for token in FORBIDDEN_REPORT_TOKENS:
        assert token not in serialized


def test_regime_forecastability_is_consistent_with_transition_and_stability():
    report = _report()

    assert report["model_consistency"]["state_label_rows_match"] is True
    assert report["model_consistency"]["unique_states_match_transition_model"] is True
    assert (
        report["model_consistency"]["per_symbol_stay_matches_transition_model"] is True
    )
    assert report["model_consistency"]["per_symbol_mismatch_count"] == 0


def test_regime_forecastability_outputs_hazard_and_lead_lag_structure():
    report = _report()

    stable_state = report["forecastability_score_per_state"]["LOW_UP_STABLE"]
    assert stable_state["stay_probability"] > 0.0
    assert stable_state["forecastability_above_random"] is True
    assert report["hazard_curves"]["LOW_UP_STABLE"]["cumulative_exit_probability"]
    assert (
        report["lead_lag_signal_check"]["per_lead_window"]["1"]["pre_shift_samples"] > 0
    )
    assert (
        report["cross_symbol_comparison"]["per_symbol"]["BTCUSDT"]["transition_count"]
        == 5
    )


def test_regime_forecastability_writes_required_artifact(tmp_path):
    labels = _labels()
    transition_model = build_state_transition_model(labels)
    stability_model = build_state_stability_model(
        labels=labels,
        transition_model=transition_model,
        dataset_rows=len(labels),
    )
    label_path = tmp_path / "market_state_labeling_v1.json"
    transition_path = tmp_path / "state_transition_model_v1.json"
    stability_path = tmp_path / "state_stability_model_v1.json"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()

    label_path.write_text(json.dumps({"state_labels": labels}), encoding="utf-8")
    transition_path.write_text(json.dumps(transition_model), encoding="utf-8")
    stability_path.write_text(json.dumps(stability_model), encoding="utf-8")
    _write_dataset(dataset_dir / "candles.csv", rows=len(labels))

    report = run_regime_forecastability(
        label_path,
        transition_model_path=transition_path,
        stability_model_path=stability_path,
        dataset_path=dataset_dir,
        output_dir=tmp_path,
    )

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["dataset_rows"] == len(labels)
    assert report["state_label_rows"] == len(labels)
    assert report["baseline_random_comparison"]["forecastability_above_random"] is True


def _report() -> dict[str, object]:
    labels = _labels()
    transition_model = build_state_transition_model(labels)
    stability_model = build_state_stability_model(
        labels=labels,
        transition_model=transition_model,
        dataset_rows=len(labels),
    )
    return build_regime_forecastability_report(
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        dataset_rows=len(labels),
    )


def _labels():
    btc_states = (
        ("LOW", "UP", "STABLE"),
        ("LOW", "UP", "STABLE"),
        ("LOW", "UP", "STABLE"),
        ("MID", "FLAT", "TRANSITIONAL"),
        ("MID", "FLAT", "TRANSITIONAL"),
        ("HIGH", "DOWN", "CHAOTIC"),
    )
    eth_states = (
        ("LOW", "UP", "STABLE"),
        ("LOW", "UP", "STABLE"),
        ("MID", "FLAT", "TRANSITIONAL"),
        ("MID", "FLAT", "TRANSITIONAL"),
        ("MID", "FLAT", "TRANSITIONAL"),
        ("LOW", "UP", "STABLE"),
    )
    return tuple(
        _label(symbol, index, state)
        for symbol, states in (("BTCUSDT", btc_states), ("ETHUSDT", eth_states))
        for index, state in enumerate(states)
    )


def _label(symbol: str, index: int, state: tuple[str, str, str]) -> dict[str, object]:
    return {
        "event_id": f"{symbol}-{index}",
        "symbol": symbol,
        "timestamp": f"2024-01-01T0{index}:00:00Z",
        "state": {
            "volatility": state[0],
            "trend": state[1],
            "stress": state[2],
        },
    }


def _write_dataset(path: Path, *, rows: int) -> None:
    body = "\n".join(
        f"2024-01-01T00:{index:02d}:00Z,BTCUSDT,100,101,99,100,{1000 + index},accepted"
        for index in range(rows)
    )
    path.write_text(
        "timestamp,symbol,open,high,low,close,volume,simulation_status\n" + body + "\n",
        encoding="utf-8",
    )
