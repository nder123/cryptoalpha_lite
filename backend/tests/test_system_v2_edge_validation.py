import json
import math
from pathlib import Path

from scripts.behavior_validation.feature_transform import generate_signal_v2
from scripts.behavior_validation.system_v2_edge_runner import (
    run_system_v2_edge_validation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"
MODES = ("random", "naive", "system")
WINDOWS = ("early", "mid", "late")


def test_signal_v2_is_compatible_with_existing_decision_mapping():
    from scripts.behavior_validation.data_adapter import (
        load_historical_data,
        normalize_dataset,
    )

    signals = generate_signal_v2(normalize_dataset(load_historical_data(FIXTURE_DIR)))

    assert all("signal_strength" in signal for signal in signals)
    assert all("signal_sensitivity" in signal for signal in signals)
    assert all("signal_delta" in signal for signal in signals)
    assert all("open" in signal and "close" in signal for signal in signals)


def test_system_v2_edge_runner_writes_stable_schema(tmp_path: Path):
    report = run_system_v2_edge_validation(FIXTURE_DIR, output_dir=tmp_path)
    artifact = json.loads((tmp_path / "system_v2_edge_report.json").read_text())

    assert report == artifact
    assert set(report) == {*MODES, "stability", "windows", "case"}
    assert set(report["windows"]) == set(WINDOWS)
    for mode in MODES:
        assert set(report[mode]) == {
            "mean_hit_rate",
            "variance",
            "mean_stability_score",
            "mean_execution_rate",
        }
    assert _is_finite(report)


def test_system_v2_runs_identically_across_seeds(tmp_path: Path):
    report = run_system_v2_edge_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["system"]["variance"] == 0.0
    assert report["stability"]["system"] == "stable"


def test_system_v2_metrics_are_comparable(tmp_path: Path):
    report = run_system_v2_edge_validation(FIXTURE_DIR, output_dir=tmp_path)
    keys = set(report["system"])

    assert set(report["random"]) == keys
    assert set(report["naive"]) == keys
    assert report["system"]["mean_execution_rate"] == 1.0
    assert report["system"]["mean_stability_score"] == 1.0


def test_system_v2_case_is_deterministic(tmp_path: Path):
    first = run_system_v2_edge_validation(FIXTURE_DIR, output_dir=tmp_path / "first")
    second = run_system_v2_edge_validation(FIXTURE_DIR, output_dir=tmp_path / "second")

    assert first == second
    assert first["case"] in {
        "CASE_A_EDGE_EXISTS",
        "CASE_B_NO_EDGE",
        "CASE_C_WEAK_EDGE",
    }


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
