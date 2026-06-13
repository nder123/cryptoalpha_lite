import json
import math
from pathlib import Path

from scripts.behavior_validation.baseline_generators import (
    generate_naive_momentum,
    generate_random_decisions,
)
from scripts.behavior_validation.comparison_metrics import build_comparison_metrics
from scripts.behavior_validation.edge_validation_runner import run_edge_validation

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"
MODES = ("random", "naive", "system")
METRIC_KEYS = {
    "hit_rate",
    "directional_consistency",
    "stability_score",
    "execution_acceptance_ratio",
}


def test_baseline_generators_are_deterministic():
    signals = (
        {
            "signal_id": "signal-1",
            "symbol": "BTCUSDT",
            "timestamp": "2026-01-01T00:00:00Z",
            "open": 10.0,
            "close": 11.0,
            "simulation_status": "accepted",
        },
        {
            "signal_id": "signal-2",
            "symbol": "BTCUSDT",
            "timestamp": "2026-01-01T00:01:00Z",
            "open": 11.0,
            "close": 10.0,
            "simulation_status": "rejected",
        },
    )

    assert generate_random_decisions(signals, seed=7) == generate_random_decisions(
        signals,
        seed=7,
    )
    assert [decision["direction"] for decision in generate_naive_momentum(signals)] == [
        "long",
        "short",
    ]


def test_comparison_metrics_are_finite_and_use_metrics_v1():
    signals = (
        {
            "signal_id": "signal-1",
            "outcome_direction": "long",
            "symbol": "BTCUSDT",
            "timestamp": "2026-01-01T00:00:00Z",
        },
    )
    decisions = (
        {
            "decision_id": "decision-1",
            "source_signal_id": "signal-1",
            "direction": "long",
        },
    )
    executions = ({"decision_id": "decision-1", "status": "accepted"},)
    metrics = build_comparison_metrics(
        signals=signals,
        decisions=decisions,
        executions=executions,
        metrics_v1={
            "acceptance_ratio": 1.0,
            "empty_windows": 0,
            "missing_data_windows": 0,
            "processing_failures": 0,
            "signals_per_window": {"2026-01-01T00:00:00Z": 1},
        },
    )

    assert metrics == {
        "hit_rate": 1.0,
        "directional_consistency": 0.0,
        "stability_score": 1.0,
        "execution_acceptance_ratio": 1.0,
    }
    assert _is_finite(metrics)


def test_edge_validation_generates_stable_schema_and_artifact(tmp_path: Path):
    report = run_edge_validation(FIXTURE_DIR, output_dir=tmp_path, seed=11)
    artifact = json.loads((tmp_path / "edge_report.json").read_text())

    assert report == artifact
    assert set(report) == {*MODES, "winner"}
    assert report["winner"] in {*MODES, "none"}
    for mode in MODES:
        assert METRIC_KEYS.issubset(report[mode])
        assert "metrics_v1" in report[mode]
        assert report[mode]["metrics_v1"]["signals_generated"] == 10
        assert _is_finite(report[mode])


def test_edge_validation_run_is_deterministic(tmp_path: Path):
    first = run_edge_validation(FIXTURE_DIR, output_dir=tmp_path / "first", seed=3)
    second = run_edge_validation(FIXTURE_DIR, output_dir=tmp_path / "second", seed=3)

    assert first == second


def test_system_pipeline_is_compared_with_baselines(tmp_path: Path):
    report = run_edge_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["random"]["metrics_v1"]["decisions_generated"] == 10
    assert report["naive"]["metrics_v1"]["decisions_generated"] == 10
    assert report["system"]["metrics_v1"]["decisions_generated"] == 10
    assert report["naive"]["hit_rate"] >= report["system"]["hit_rate"]


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
