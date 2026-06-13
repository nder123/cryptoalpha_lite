import json
import math
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.decision_isolation_runner import (
    run_decision_isolation,
    run_force_pass_test,
    run_signal_echo_test,
    run_threshold_relaxation_test,
)
from scripts.behavior_validation.evaluation_runner import _generate_signals

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"


def test_force_pass_creates_non_zero_decision_flow():
    result = run_force_pass_test(_signals())

    assert result["decision_flow"] == "alive"
    assert result["decisions_generated"] == 10
    assert result["executions_attempted"] == 10
    assert result["metrics_v1"]["decision_rate"] == 1.0


def test_threshold_relaxation_creates_non_zero_decision_flow():
    result = run_threshold_relaxation_test(_signals(), threshold=0.001)

    assert result["decision_flow"] == "alive"
    assert result["decisions_generated"] == 8
    assert result["executions_attempted"] == 8
    assert result["metrics_v1"]["decision_rate"] == 0.8


def test_signal_echo_preserves_signal_to_decision_relation():
    result = run_signal_echo_test(_signals())

    assert result["decision_flow"] == "alive"
    assert result["signal_decision_correlation"] == 1.0
    assert result["decisions_generated"] == 10


def test_decision_isolation_runner_writes_stable_schema(tmp_path: Path):
    report = run_decision_isolation(FIXTURE_DIR, output_dir=tmp_path)
    artifact = json.loads((tmp_path / "decision_isolation.json").read_text())

    assert report == artifact
    assert set(report) == {
        "force_pass",
        "threshold_relaxation",
        "signal_echo",
        "case",
    }
    assert report["case"] == "CASE_A_DECISION_LAYER_BLOCKS_SIGNAL_INFORMATION"
    assert report["force_pass"]["executions_attempted"] == 10
    assert report["threshold_relaxation"]["executions_attempted"] == 8
    assert report["signal_echo"]["signal_decision_correlation"] == 1.0
    assert _is_finite(report)


def test_decision_isolation_runner_is_deterministic(tmp_path: Path):
    first = run_decision_isolation(FIXTURE_DIR, output_dir=tmp_path / "first")
    second = run_decision_isolation(FIXTURE_DIR, output_dir=tmp_path / "second")

    assert first == second


def _signals() -> tuple[dict[str, object], ...]:
    data = normalize_dataset(load_historical_data(FIXTURE_DIR))
    base_signals = _generate_signals(data)
    return tuple(
        {
            **signal,
            "signal_magnitude": _magnitude(row),
        }
        for signal, row in zip(base_signals, data, strict=True)
    )


def _magnitude(row: dict[str, object]) -> float:
    open_price = _float_value(row.get("open"))
    close_price = _float_value(row.get("close"))
    if open_price == 0.0:
        return 0.0
    return abs(close_price - open_price) / open_price


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
