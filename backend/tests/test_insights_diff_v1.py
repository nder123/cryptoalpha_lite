import json
from pathlib import Path

from scripts.behavior_validation.evaluation_runner import run_historical_evaluation
from scripts.behavior_validation.insights_diff_v1 import (
    diff_insights,
    diff_insights_files,
)
from scripts.behavior_validation.run_insights_diff import main as diff_cli_main

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"


def test_insights_diff_v1_stable_case():
    diff = diff_insights(
        _insights(0.50, 0.40, 0.90, "stable_regime"),
        _insights(0.52, 0.42, 0.91, "stable_regime"),
    )

    assert diff["decision_efficiency_delta"] == 0.020000000000000018
    assert diff["execution_friction_delta"] == 0.019999999999999962
    assert diff["stability_index_delta"] == 0.010000000000000009
    assert diff["drift_classification"] == "STABLE"


def test_insights_diff_v1_improving_case():
    diff = diff_insights(
        _insights(0.50, 0.40, 0.80, "high_noise"),
        _insights(0.60, 0.30, 0.90, "stable_regime"),
    )

    assert diff["drift_classification"] == "IMPROVING"


def test_insights_diff_v1_degrading_case():
    diff = diff_insights(
        _insights(0.60, 0.30, 0.90, "stable_regime"),
        _insights(0.50, 0.40, 0.90, "high_noise"),
    )

    assert diff["drift_classification"] == "DEGRADING"


def test_insights_diff_v1_chaotic_case_has_priority():
    diff = diff_insights(
        _insights(0.90, 0.10, 0.95, "stable_regime"),
        _insights(0.60, 0.50, 0.60, "high_noise"),
    )

    assert diff["drift_classification"] == "CHAOTIC"


def test_insights_diff_v1_regime_transition_mapping():
    diff = diff_insights(
        _insights(0.30, 0.60, 0.80, "high_noise"),
        _insights(0.45, 0.50, 0.85, "active_regime"),
    )

    assert diff["regime_transition"] == {
        "from": "high_noise",
        "to": "active_regime",
    }


def test_insights_diff_v1_file_output_is_deterministic(tmp_path: Path):
    previous_path = tmp_path / "previous.json"
    current_path = tmp_path / "current.json"
    previous_path.write_text(
        json.dumps(_insights(0.50, 0.40, 0.80, "high_noise")),
        encoding="utf-8",
    )
    current_path.write_text(
        json.dumps(_insights(0.60, 0.30, 0.90, "stable_regime")),
        encoding="utf-8",
    )

    first = diff_insights_files(previous_path, current_path)
    second = diff_insights_files(previous_path, current_path)

    assert first == second


def test_run_insights_diff_cli_prints_json(
    tmp_path: Path,
    capsys,
    monkeypatch,
):
    previous_path = tmp_path / "previous.json"
    current_path = tmp_path / "current.json"
    previous_path.write_text(
        json.dumps(_insights(0.50, 0.40, 0.80, "high_noise")),
        encoding="utf-8",
    )
    current_path.write_text(
        json.dumps(_insights(0.60, 0.30, 0.90, "stable_regime")),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_insights_diff.py",
            str(previous_path),
            str(current_path),
        ],
    )

    diff_cli_main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["drift_classification"] == "IMPROVING"


def test_insights_diff_artifact_is_disabled_by_default(tmp_path: Path):
    run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)

    assert not (tmp_path / "insights_diff.json").exists()


def test_insights_diff_artifact_can_be_enabled(
    tmp_path: Path,
    monkeypatch,
):
    previous_path = tmp_path / "previous.json"
    previous_path.write_text(
        json.dumps(_insights(0.90, 0.10, 0.95, "stable_regime")),
        encoding="utf-8",
    )
    monkeypatch.setenv("ENABLE_INSIGHTS_DIFF", "true")
    monkeypatch.setenv("PREVIOUS_INSIGHTS_PATH", str(previous_path))

    run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)

    diff = json.loads((tmp_path / "insights_diff.json").read_text())
    assert diff["drift_classification"] == "CHAOTIC"


def _insights(
    decision_efficiency: float,
    execution_friction: float,
    stability_index: float,
    activity_profile: str,
) -> dict[str, object]:
    return {
        "decision_efficiency": decision_efficiency,
        "execution_friction": execution_friction,
        "stability_index": stability_index,
        "activity_profile": activity_profile,
    }
