from scripts.behavior_validation.full_dataset_verdict_v1 import (
    build_full_dataset_verdict,
)


def test_full_dataset_verdict_reports_no_edge_when_economic_edge_is_negative():
    report = build_full_dataset_verdict(
        evaluation=_evaluation(),
        system_v2=_system_v2(system_hit_rate=0.55, case="CASE_A_EDGE_EXISTS"),
        regime=_regime(classification="stable"),
        economic={
            "edge_score": -0.01,
            "cost_adjusted_pnl": -1.0,
            "regime_pnl": {"low": -0.1, "mid": -0.2, "high": -0.7},
        },
    )

    assert report["dataset_rows"] == 4464
    assert report["symbols"] == 6
    assert report["verdict"] == "NO_EDGE"
    assert report["edge_score"] == -0.01


def test_full_dataset_verdict_reports_stable_edge_when_all_checks_pass():
    report = build_full_dataset_verdict(
        evaluation=_evaluation(),
        system_v2=_system_v2(system_hit_rate=0.6, case="CASE_A_EDGE_EXISTS"),
        regime=_regime(classification="stable"),
        economic={
            "edge_score": 0.01,
            "cost_adjusted_pnl": 1.0,
            "regime_pnl": {"low": 0.2, "mid": 0.3, "high": 0.5},
        },
    )

    assert report["verdict"] == "STABLE_EDGE"


def test_full_dataset_verdict_reports_weak_edge_for_positive_but_non_stable_case():
    report = build_full_dataset_verdict(
        evaluation=_evaluation(),
        system_v2=_system_v2(system_hit_rate=0.6, case="CASE_C_WEAK_EDGE"),
        regime=_regime(classification="partial"),
        economic={
            "edge_score": 0.01,
            "cost_adjusted_pnl": 1.0,
            "regime_pnl": {"low": 0.2, "mid": 0.3, "high": 0.5},
        },
    )

    assert report["verdict"] == "WEAK_EDGE"


def _evaluation() -> dict[str, object]:
    return {
        "metrics_v1": {
            "signals_generated": 4464,
            "signals_per_symbol": {
                "BTCUSDT": 744,
                "DOGEUSDT": 744,
                "ETHUSDT": 744,
                "LINKUSDT": 744,
                "SOLUSDT": 744,
                "XRPUSDT": 744,
            },
        }
    }


def _system_v2(*, system_hit_rate: float, case: str) -> dict[str, object]:
    return {
        "case": case,
        "random": {"mean_hit_rate": 0.5, "variance": 0.0},
        "naive": {"mean_hit_rate": 0.49, "variance": 0.0},
        "system": {"mean_hit_rate": system_hit_rate, "variance": 0.0},
        "stability": {"system": "stable"},
    }


def _regime(*, classification: str) -> dict[str, object]:
    return {
        "classification": classification,
        "stability": 0.0,
        "regimes": {
            "low_vol": {"system": 0.6, "naive": 0.5, "random": 0.5},
            "mid_vol": {"system": 0.6, "naive": 0.5, "random": 0.5},
            "high_vol": {"system": 0.6, "naive": 0.5, "random": 0.5},
        },
    }
