import json
import math
from pathlib import Path

from scripts.behavior_validation.statistical_edge_runner import (
    DEFAULT_SEEDS,
    run_statistical_edge_validation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"
MODES = ("random", "naive", "system")
WINDOWS = ("early", "mid", "late")


def test_statistical_edge_runner_writes_stable_schema(tmp_path: Path):
    report = run_statistical_edge_validation(FIXTURE_DIR, output_dir=tmp_path)
    artifact = json.loads((tmp_path / "statistical_edge_v1.json").read_text())

    assert report == artifact
    assert set(report) == {*MODES, "stability", "windows", "case"}
    assert set(report["stability"]) == set(MODES)
    assert set(report["windows"]) == set(WINDOWS)
    for mode in MODES:
        assert set(report[mode]) == {
            "mean_hit_rate",
            "variance",
            "mean_decision_density",
            "mean_execution_rate",
        }
    assert _is_finite(report)


def test_system_is_deterministic_across_seeds(tmp_path: Path):
    report = run_statistical_edge_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["system"]["variance"] == 0.0
    assert report["stability"]["system"] == "stable"


def test_metrics_are_comparable_across_baselines(tmp_path: Path):
    report = run_statistical_edge_validation(FIXTURE_DIR, output_dir=tmp_path)
    keys = set(report["system"])

    assert set(report["random"]) == keys
    assert set(report["naive"]) == keys
    assert report["system"]["mean_execution_rate"] == 1.0
    assert report["random"]["mean_execution_rate"] == 1.0
    assert report["naive"]["mean_execution_rate"] == 1.0


def test_statistical_case_identifies_stable_no_edge(tmp_path: Path):
    report = run_statistical_edge_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["system"]["mean_hit_rate"] < report["random"]["mean_hit_rate"]
    assert report["case"] == "CASE_A_SYSTEM_BELOW_RANDOM_STABLE"


def test_run_is_deterministic_for_same_seed_set(tmp_path: Path):
    first = run_statistical_edge_validation(
        FIXTURE_DIR,
        output_dir=tmp_path / "first",
        seeds=DEFAULT_SEEDS,
    )
    second = run_statistical_edge_validation(
        FIXTURE_DIR,
        output_dir=tmp_path / "second",
        seeds=DEFAULT_SEEDS,
    )

    assert first == second


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
