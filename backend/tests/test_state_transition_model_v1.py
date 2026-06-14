from pathlib import Path

from scripts.behavior_validation.state_transition_model_v1 import (
    SUMMARY_FILENAME,
    build_state_transition_model,
    run_state_transition_model,
    state_sequences_by_symbol,
)

FORBIDDEN_REPORT_KEYS = {
    "edge",
    "pnl",
    "decision",
    "evaluation",
    "economic",
}


def test_state_transition_model_is_deterministic_and_reproducible():
    labels = _labels()

    first = build_state_transition_model(labels)
    second = build_state_transition_model(labels)

    assert first == second
    assert first["entropy_metrics"]["global"]["entropy_below_uniform"] is True


def test_state_transition_model_reconstructs_sequences_consistently():
    sequences = state_sequences_by_symbol(tuple(reversed(_labels())))

    assert sequences["BTCUSDT"] == (
        "LOW_UP_STABLE",
        "LOW_UP_STABLE",
        "MID_FLAT_TRANSITIONAL",
        "MID_FLAT_TRANSITIONAL",
        "HIGH_DOWN_CHAOTIC",
    )
    assert sequences["ETHUSDT"][0] == "LOW_UP_STABLE"


def test_state_transition_model_has_no_forbidden_layer_leakage():
    report = build_state_transition_model(_labels())
    serialized = str(report).lower()
    source = Path(
        "backend/scripts/behavior_validation/state_transition_model_v1.py"
    ).read_text(encoding="utf-8")

    assert "evaluation_runner" not in source
    for forbidden_key in FORBIDDEN_REPORT_KEYS:
        assert forbidden_key not in serialized


def test_state_transition_model_reports_stability_and_cross_symbol_structure():
    report = build_state_transition_model(_labels())

    assert report["stability_of_transitions"]["global"]["diagonal_dominance"] > 0.0
    assert (
        report["stability_of_transitions"]["global"]["diagonal_dominance_observed"]
        is True
    )
    assert "BTCUSDT" in report["cross_symbol_similarity_matrix"]
    assert "ETHUSDT" in report["btc_vs_alts_structural_divergence"]["per_alt_symbol"]
    assert (
        report["baseline_comparison"]["global"][
            "observed_more_predictable_than_uniform"
        ]
        is True
    )


def test_state_transition_model_writes_required_artifact(tmp_path):
    label_path = tmp_path / "market_state_labeling_v1.json"
    label_path.write_text(
        _labels_payload(),
        encoding="utf-8",
    )

    report = run_state_transition_model(label_path, output_dir=tmp_path)

    artifact = tmp_path / SUMMARY_FILENAME
    assert artifact.exists()
    assert report["input_rows"] == 10
    assert report["symbols"] == 2
    assert report["global_transition_matrix"]


def _labels_payload() -> str:
    import json

    return json.dumps({"state_labels": _labels()})


def _labels():
    btc_states = (
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
        ("LOW", "UP", "STABLE"),
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
