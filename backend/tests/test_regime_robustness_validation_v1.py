import json
import math
from pathlib import Path

from scripts.behavior_validation.regime_robustness_runner import (
    run_regime_robustness_validation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"
REGIMES = ("low_vol", "mid_vol", "high_vol")
METRICS = ("system", "naive", "random", "variance")


def test_regime_robustness_writes_expected_schema(tmp_path: Path):
    report = run_regime_robustness_validation(FIXTURE_DIR, output_dir=tmp_path)
    artifact = json.loads((tmp_path / "regime_robustness_v1.json").read_text())

    assert report == artifact
    assert set(report) == {"regimes", "stability", "classification"}
    assert set(report["regimes"]) == set(REGIMES)
    for regime in REGIMES:
        assert set(report["regimes"][regime]) == set(METRICS)
    assert _is_finite(report)


def test_regime_robustness_is_deterministic(tmp_path: Path):
    first = run_regime_robustness_validation(FIXTURE_DIR, output_dir=tmp_path / "a")
    second = run_regime_robustness_validation(FIXTURE_DIR, output_dir=tmp_path / "b")

    assert first == second


def test_regime_classification_is_bounded(tmp_path: Path):
    report = run_regime_robustness_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["classification"] in {"unstable", "partial", "stable"}
    assert report["stability"] >= 0.0


def test_regime_metrics_are_comparable(tmp_path: Path):
    report = run_regime_robustness_validation(FIXTURE_DIR, output_dir=tmp_path)

    for regime in report["regimes"].values():
        assert 0.0 <= regime["system"] <= 1.0
        assert 0.0 <= regime["naive"] <= 1.0
        assert 0.0 <= regime["random"] <= 1.0
        assert regime["variance"] >= 0.0


def test_fixture_regime_result_confirms_regime_robustness(tmp_path: Path):
    report = run_regime_robustness_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert (
        report["regimes"]["low_vol"]["system"] >= report["regimes"]["low_vol"]["naive"]
    )
    assert (
        report["regimes"]["mid_vol"]["system"] > report["regimes"]["mid_vol"]["naive"]
    )
    assert (
        report["regimes"]["high_vol"]["system"] > report["regimes"]["high_vol"]["naive"]
    )
    assert report["classification"] == "stable"


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
