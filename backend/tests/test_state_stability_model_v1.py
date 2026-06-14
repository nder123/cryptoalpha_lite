import json
from pathlib import Path

from scripts.behavior_validation.state_stability_model_v1 import (
    SUMMARY_FILENAME,
    build_state_stability_model,
    run_state_stability_model,
    state_runs_by_symbol,
)
from scripts.behavior_validation.state_transition_model_v1 import (
    build_state_transition_model,
    state_sequences_by_symbol,
)

FORBIDDEN_SOURCE_TOKENS = ("evaluation_runner", "economic_closure")
FORBIDDEN_REPORT_TOKENS = ("decision", "pnl", "reward")


def test_state_stability_model_is_deterministic_and_reproducible():
    labels = _labels()
    transition_model = build_state_transition_model(labels)

    first = build_state_stability_model(
        labels=labels,
        transition_model=transition_model,
        dataset_rows=len(labels),
    )
    second = build_state_stability_model(
        labels=labels,
        transition_model=transition_model,
        dataset_rows=len(labels),
    )

    assert first == second
    assert (
        first["baseline_random_model_comparison"]["global"]["stability_above_random"]
        is True
    )


def test_state_stability_model_reconstructs_state_runs_consistently():
    sequences = state_sequences_by_symbol(_labels())
    runs = state_runs_by_symbol(sequences)

    assert tuple(run["duration"] for run in runs["BTCUSDT"]) == (3, 2, 1)
    assert runs["BTCUSDT"][0]["state"] == "LOW_UP_STABLE"
    assert runs["BTCUSDT"][0]["next_state"] == "MID_FLAT_TRANSITIONAL"


def test_state_stability_model_has_no_restricted_layer_leakage():
    source = Path(
        "backend/scripts/behavior_validation/state_stability_model_v1.py"
    ).read_text(encoding="utf-8")
    report = build_state_stability_model(
        labels=_labels(),
        transition_model=build_state_transition_model(_labels()),
        dataset_rows=len(_labels()),
    )
    serialized = str(report).lower()

    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source
    for token in FORBIDDEN_REPORT_TOKENS:
        assert token not in serialized


def test_state_stability_model_matches_transition_model_counts():
    labels = _labels()
    report = build_state_stability_model(
        labels=labels,
        transition_model=build_state_transition_model(labels),
        dataset_rows=len(labels),
    )

    assert (
        report["transition_model_consistency"]["matches_state_transition_model_v1"]
        is True
    )
    assert report["transition_model_consistency"]["mismatch_count"] == 0
    assert (
        report["stability_ranking_of_states"]["most_persistent"][0]["mean_duration"]
        > report["stability_ranking_of_states"]["most_transient"][0]["mean_duration"]
    )


def test_state_stability_model_writes_required_artifact(tmp_path):
    labels = _labels()
    label_path = tmp_path / "market_state_labeling_v1.json"
    transition_path = tmp_path / "state_transition_model_v1.json"
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()

    label_path.write_text(json.dumps({"state_labels": labels}), encoding="utf-8")
    transition_path.write_text(
        json.dumps(build_state_transition_model(labels)),
        encoding="utf-8",
    )
    _write_dataset(dataset_dir / "candles.csv", rows=len(labels))

    report = run_state_stability_model(
        label_path,
        transition_model_path=transition_path,
        dataset_path=dataset_dir,
        output_dir=tmp_path,
    )

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["dataset_rows"] == len(labels)
    assert report["state_label_rows"] == len(labels)
    assert report["exit_probability_distributions"]
    assert report["half_life_estimates"]["histogram_per_state_class"]


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
