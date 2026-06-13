from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.evaluation_runner import (
    _generate_decisions,
    _generate_signals,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"


def test_decision_score_preserves_weighted_signal_information():
    signals = _signals()
    decisions = _generate_decisions(signals)

    assert (
        _same_value_ratio(_weighted_signals(signals), _decision_scores(decisions))
        == 1.0
    )


def test_decision_output_is_non_binary_and_has_variance():
    scores = _decision_scores(_generate_decisions(_signals()))

    assert len(set(scores)) > 2
    assert set(scores) != {0.0, 1.0}
    assert max(scores) - min(scores) > 0.0


def test_decision_representation_does_not_change_pipeline_counts(tmp_path: Path):
    from scripts.behavior_validation.evaluation_runner import run_historical_evaluation

    report = run_historical_evaluation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["signals"] == 10
    assert report["decisions"] == 10
    assert report["executions"] == 10
    assert report["metrics_v1"]["decision_rate"] == 1.0


def _signals() -> tuple[dict[str, object], ...]:
    return _generate_signals(normalize_dataset(load_historical_data(FIXTURE_DIR)))


def _weighted_signals(signals: tuple[dict[str, object], ...]) -> tuple[float, ...]:
    return tuple(
        0.5 * _float_value(signal.get("signal_strength"))
        + 0.3 * _float_value(signal.get("signal_sensitivity"))
        + 0.2 * _float_value(signal.get("signal_delta"))
        for signal in signals
    )


def _decision_scores(decisions: tuple[dict[str, object], ...]) -> tuple[float, ...]:
    return tuple(_float_value(decision.get("decision_score")) for decision in decisions)


def _same_value_ratio(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right:
        return 0.0
    return sum(
        1
        for left_value, right_value in zip(left, right, strict=True)
        if left_value == right_value
    ) / len(left)


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0
