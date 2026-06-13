import json
import math
from pathlib import Path

from scripts.behavior_validation.economic_closure_runner import (
    run_economic_closure_validation,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior_validation"
REGIMES = ("low", "mid", "high")


def test_economic_closure_writes_minimal_schema(tmp_path: Path):
    report = run_economic_closure_validation(FIXTURE_DIR, output_dir=tmp_path)
    artifact = json.loads((tmp_path / "economic_closure_v1.json").read_text())

    assert report == artifact
    assert set(report) == {
        "total_pnl",
        "regime_pnl",
        "cost_adjusted_pnl",
        "edge_score",
    }
    assert set(report["regime_pnl"]) == set(REGIMES)
    assert _is_finite(report)


def test_economic_closure_is_deterministic(tmp_path: Path):
    first = run_economic_closure_validation(FIXTURE_DIR, output_dir=tmp_path / "a")
    second = run_economic_closure_validation(FIXTURE_DIR, output_dir=tmp_path / "b")

    assert first == second


def test_cost_adjusted_pnl_includes_transaction_costs_and_penalties(tmp_path: Path):
    report = run_economic_closure_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["cost_adjusted_pnl"] < report["total_pnl"]


def test_regime_pnl_distinguishes_regime_economic_consequence(tmp_path: Path):
    report = run_economic_closure_validation(FIXTURE_DIR, output_dir=tmp_path)
    regime_values = tuple(report["regime_pnl"][regime] for regime in REGIMES)

    assert len(set(regime_values)) > 1


def test_edge_score_is_average_cost_adjusted_reward(tmp_path: Path):
    report = run_economic_closure_validation(FIXTURE_DIR, output_dir=tmp_path)

    assert report["edge_score"] == report["cost_adjusted_pnl"] / 10


def _is_finite(payload: dict[str, object]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not _is_finite(value):
                return False
        elif isinstance(value, float) and math.isnan(value):
            return False
    return True
