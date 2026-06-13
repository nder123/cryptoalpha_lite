import json
import math
from pathlib import Path

from scripts.behavior_validation.evaluation_runner import run_historical_evaluation
from scripts.behavior_validation.insights_v1 import build_insights_v1

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"


def test_insights_v1_calculates_expected_values():
    insights = build_insights_v1(
        {
            "signals_generated": 10,
            "decisions_generated": 5,
            "executions_attempted": 5,
            "executions_rejected": 2,
            "empty_windows": 1,
            "processing_failures": 1,
            "signals_per_window": {
                "window-1": 2,
                "window-2": 3,
                "window-3": 5,
                "window-4": 0,
            },
        }
    )

    assert insights == {
        "decision_efficiency": 0.5,
        "execution_friction": 0.4,
        "stability_index": 0.5,
        "activity_profile": "active_regime",
    }


def test_insights_v1_has_no_nan_or_division_errors():
    insights = build_insights_v1(
        {
            "signals_generated": 0,
            "decisions_generated": 0,
            "executions_attempted": 0,
            "executions_rejected": 0,
            "empty_windows": 0,
            "processing_failures": 0,
            "signals_per_window": {},
        }
    )

    assert insights["decision_efficiency"] == 0.0
    assert insights["execution_friction"] == 0.0
    assert insights["stability_index"] == 0.0
    assert insights["activity_profile"] == "inactive"
    assert all(
        not math.isnan(value) for value in insights.values() if isinstance(value, float)
    )


def test_insights_v1_is_consistent_with_metrics_v1(tmp_path: Path):
    report = run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)
    metrics_v1 = report["metrics_v1"]
    insights = build_insights_v1(metrics_v1)

    assert insights["decision_efficiency"] == metrics_v1["decision_rate"]
    assert insights["execution_friction"] == 0.4
    assert insights["stability_index"] == 1.0
    assert insights["activity_profile"] == "stable_regime"


def test_insights_v1_run_is_deterministic(tmp_path: Path):
    report = run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)

    first = build_insights_v1(report["metrics_v1"])
    second = build_insights_v1(report["metrics_v1"])

    assert first == second


def test_insights_v1_is_debug_artifact_only(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ENABLE_BEHAVIOR_INSIGHTS_DEBUG", "true")

    run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)

    insights = json.loads((tmp_path / "insights.json").read_text())
    assert insights["activity_profile"] == "stable_regime"
