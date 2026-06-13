import json
import math
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.diagnosis_runner import (
    check_data_variance,
    check_decision_sensitivity,
    check_signal_sensitivity,
    run_diagnosis,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"


def test_data_variance_detects_non_flat_fixture_data():
    data = normalize_dataset(load_historical_data(FIXTURE_DIR))
    result = check_data_variance(data)

    assert result["classification"] == "medium"
    assert result["price_variance"] > 0.0
    assert result["volatility_proxy"] > 0.0
    assert result["trend_strength_proxy"] > 0.0
    assert _is_finite(result)


def test_signal_sensitivity_detects_shuffle_response():
    data = normalize_dataset(load_historical_data(FIXTURE_DIR))
    result = check_signal_sensitivity(data)

    assert result == {
        "classification": "sensitive",
        "changed_ratio": 1.0,
    }


def test_decision_sensitivity_detects_reactive_mapping():
    data = normalize_dataset(load_historical_data(FIXTURE_DIR))
    result = check_decision_sensitivity(data)

    assert result == {
        "classification": "reactive",
        "changed_ratio": 1.0,
    }


def test_diagnosis_runner_writes_stable_schema(tmp_path: Path):
    report = run_diagnosis(FIXTURE_DIR, output_dir=tmp_path)
    artifact = json.loads((tmp_path / "diagnosis.json").read_text())

    assert report == artifact
    assert report["data"] == "medium"
    assert report["signal"] == "sensitive"
    assert report["decision"] == "reactive"
    assert set(report) == {"data", "signal", "decision", "details"}
    assert set(report["details"]) == {"data", "signal", "decision"}
    assert _is_finite(report)


def test_diagnosis_runner_is_deterministic(tmp_path: Path):
    first = run_diagnosis(FIXTURE_DIR, output_dir=tmp_path / "first")
    second = run_diagnosis(FIXTURE_DIR, output_dir=tmp_path / "second")

    assert first == second


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
