import json
from pathlib import Path

from scripts.behavior_validation.evaluation_runner import run_evaluation
from scripts.behavior_validation.execution_simulator import simulate_execution
from scripts.behavior_validation.metrics import build_metrics
from scripts.behavior_validation.report_schema import build_report


def test_execution_simulator_supports_minimal_statuses():
    accepted = simulate_execution(
        {"decision_id": "decision-1", "simulation_status": "accepted"}
    )
    rejected = simulate_execution(
        {"decision_id": "decision-2", "simulation_status": "rejected"}
    )
    delayed = simulate_execution(
        {"decision_id": "decision-3", "simulation_status": "delayed"}
    )

    assert accepted["status"] == "accepted"
    assert rejected["status"] == "rejected"
    assert delayed["status"] == "delayed"


def test_metrics_are_minimal_counts_only():
    metrics = build_metrics(
        signals=("signal-1", "signal-2"),
        decisions=("decision-1", "decision-2"),
        executions=(
            {"decision_id": "decision-1", "status": "accepted"},
            {"decision_id": "decision-2", "status": "rejected"},
        ),
    )

    assert metrics == {
        "signals_generated": 2,
        "decisions_generated": 2,
        "executions_attempted": 2,
        "executions_simulated": 2,
        "simulation_failures": 1,
    }


def test_report_schema_is_json_serializable():
    report = build_report(
        run_id="run-1",
        signals=1,
        decisions=1,
        executions=1,
        metrics={"signals_generated": 1},
        metrics_v1={"signals_generated": 1},
    )

    assert set(report) == {
        "run_id",
        "signals",
        "decisions",
        "executions",
        "metrics",
        "metrics_v1",
    }
    assert json.loads(json.dumps(report)) == report


def test_evaluation_runner_writes_summary_and_metrics(tmp_path: Path):
    report = run_evaluation(
        run_id="test-run",
        output_dir=tmp_path,
        data=(
            {"event_id": "event-1", "simulation_status": "accepted"},
            {"event_id": "event-2", "simulation_status": "delayed"},
        ),
    )

    summary = json.loads((tmp_path / "summary.json").read_text())
    metrics = json.loads((tmp_path / "metrics.json").read_text())

    assert report == summary
    assert summary["run_id"] == "test-run"
    assert summary["signals"] == 2
    assert summary["decisions"] == 2
    assert summary["executions"] == 2
    assert metrics["executions_simulated"] == 2
    assert metrics["metrics_v1"]["signals_generated"] == 2
