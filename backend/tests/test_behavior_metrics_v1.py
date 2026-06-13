import json
from pathlib import Path

from scripts.behavior_validation.evaluation_runner import run_historical_evaluation
from scripts.behavior_validation.metrics_v1 import build_metrics_v1

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"


def test_metrics_v1_forms_non_null_metrics():
    metrics = build_metrics_v1(
        signals=(
            {
                "signal_id": "signal-1",
                "symbol": "BTCUSDT",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "signal_id": "signal-2",
                "symbol": "ETHUSDT",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        ),
        decisions=(
            {"decision_id": "decision-1"},
            {"decision_id": "decision-2"},
        ),
        executions=(
            {"decision_id": "decision-1", "status": "accepted"},
            {"decision_id": "decision-2", "status": "rejected"},
        ),
    )

    assert metrics == {
        "signals_generated": 2,
        "signals_per_symbol": {"BTCUSDT": 1, "ETHUSDT": 1},
        "signals_per_window": {"2026-01-01T00:00:00Z": 2},
        "decisions_generated": 2,
        "decision_rate": 1.0,
        "decision_density": 2.0,
        "executions_attempted": 2,
        "executions_accepted": 1,
        "executions_rejected": 1,
        "acceptance_ratio": 0.5,
        "empty_windows": 0,
        "missing_data_windows": 0,
        "processing_failures": 0,
    }
    assert all(value is not None for value in metrics.values())


def test_metrics_v1_counts_match_pipeline_counts(tmp_path: Path):
    report = run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)
    metrics = report["metrics_v1"]

    assert metrics["signals_generated"] == report["signals"]
    assert metrics["decisions_generated"] == report["decisions"]
    assert metrics["executions_attempted"] == report["decisions"]
    assert metrics["executions_accepted"] == 4
    assert metrics["executions_rejected"] == 4
    assert metrics["acceptance_ratio"] == 0.4


def test_metrics_v1_run_is_deterministic(tmp_path: Path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = run_historical_evaluation(FIXTURE_DIR, output_dir=first_dir)
    second = run_historical_evaluation(FIXTURE_DIR, output_dir=second_dir)

    assert first["metrics_v1"] == second["metrics_v1"]
    assert json.loads((first_dir / "metrics.json").read_text()) == json.loads(
        (second_dir / "metrics.json").read_text()
    )


def test_metrics_v1_does_not_change_legacy_summary_counts(tmp_path: Path):
    run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    metrics = json.loads((tmp_path / "metrics.json").read_text())

    assert summary["signals"] == 10
    assert summary["decisions"] == 10
    assert summary["executions"] == 10
    assert metrics["metrics_v1"] == summary["metrics_v1"]
