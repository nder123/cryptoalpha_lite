import json
import math
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.feature_transform import (
    generate_signal_v2,
    transform_market_features,
)
from scripts.behavior_validation.signal_space_runner import run_signal_space_comparison

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"
FEATURE_KEYS = (
    "volatility_regime",
    "market_structure",
    "delta_acceleration",
    "volatility_cluster",
    "range_behavior",
    "range_expansion",
    "normalized_deviation",
    "z_score",
    "relative_strength",
)


def test_feature_transform_generates_market_structure_features():
    features = transform_market_features(_data())

    assert len(features) == 10
    for feature_row in features:
        assert set(FEATURE_KEYS).issubset(feature_row)
        assert feature_row["volatility_regime"] in {"low", "mid", "high"}
        assert feature_row["market_structure"] in {"trend", "chop"}
        assert feature_row["range_behavior"] in {"compression", "neutral", "expansion"}
        assert _is_finite(feature_row)


def test_generate_signal_v2_is_deterministic_and_contextual():
    first = generate_signal_v2(_data())
    second = generate_signal_v2(_data())

    assert first == second
    assert len(first) == 10
    assert len({signal["signal_v2_bucket"] for signal in first}) > 2
    assert all("signal_v2_score" in signal for signal in first)


def test_signal_space_comparison_writes_schema_and_artifact(tmp_path: Path):
    report = run_signal_space_comparison(FIXTURE_DIR, output_dir=tmp_path)
    artifact = json.loads((tmp_path / "signal_space_v1.json").read_text())

    assert report == artifact
    assert set(report) == {"signal_v1", "signal_v2", "features", "delta", "winner"}
    assert report["features"] == list(FEATURE_KEYS)
    assert report["signal_v1"]["samples"] == 8
    assert report["signal_v2"]["samples"] == 8
    assert _is_finite(report)


def test_signal_v2_increases_mutual_information_proxy(tmp_path: Path):
    report = run_signal_space_comparison(FIXTURE_DIR, output_dir=tmp_path)

    assert (
        report["signal_v2"]["mutual_information_proxy"]
        >= report["signal_v1"]["mutual_information_proxy"]
    )
    assert report["winner"] in {"signal_v2", "none"}


def test_signal_space_comparison_is_deterministic(tmp_path: Path):
    first = run_signal_space_comparison(FIXTURE_DIR, output_dir=tmp_path / "first")
    second = run_signal_space_comparison(FIXTURE_DIR, output_dir=tmp_path / "second")

    assert first == second


def _data() -> tuple[dict[str, object], ...]:
    return normalize_dataset(load_historical_data(FIXTURE_DIR))


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
