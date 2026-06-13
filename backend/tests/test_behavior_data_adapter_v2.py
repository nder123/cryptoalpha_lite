import json
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.evaluation_runner import run_historical_evaluation

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"


def test_load_historical_data_reads_fixture_directory():
    rows = load_historical_data(FIXTURE_DIR)

    assert len(rows) == 10
    assert {row["symbol"] for row in rows} == {"BTCUSDT", "ETHUSDT"}
    assert rows[0]["timestamp"] == "2026-01-01T00:00:00Z"


def test_normalize_dataset_returns_runner_ready_events():
    rows = normalize_dataset(load_historical_data(FIXTURE_DIR))

    assert len(rows) == 10
    assert rows[0]["event_id"] == "BTCUSDT-2026-01-01T00:00:00Z"
    assert rows[0]["open"] == 42000.0
    assert {row["simulation_status"] for row in rows} == {
        "accepted",
        "rejected",
        "delayed",
    }


def test_historical_evaluation_generates_artifacts(tmp_path: Path):
    report = run_historical_evaluation(
        FIXTURE_DIR,
        run_id="historical-fixture-run",
        output_dir=tmp_path,
    )

    summary = json.loads((tmp_path / "summary.json").read_text())
    metrics = json.loads((tmp_path / "metrics.json").read_text())
    input_summary = json.loads((tmp_path / "input_summary.json").read_text())
    insights = json.loads((tmp_path / "insights.json").read_text())

    assert report == summary
    assert not (tmp_path / "insights_diff.json").exists()
    assert summary["signals"] == 10
    assert summary["decisions"] == 10
    assert summary["executions"] == 10
    assert metrics["signals_generated"] == 10
    assert metrics["metrics_v1"]["signals_generated"] == 10
    assert insights["activity_profile"] == "stable_regime"
    assert input_summary == {
        "rows": 10,
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "time_range": "2026-01-01T00:00:00Z..2026-01-01T00:04:00Z",
    }
