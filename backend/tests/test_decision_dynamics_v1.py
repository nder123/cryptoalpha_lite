from pathlib import Path

from scripts.behavior_validation.data_adapter import normalize_dataset
from scripts.behavior_validation.decision_dynamics_v1 import (
    SUMMARY_FILENAME,
    apply_dynamic_decision_scaling,
    build_decision_dynamics_analysis,
    run_decision_dynamics_analysis,
)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT")


def test_static_mode_preserves_existing_pipeline_behavior():
    report = build_decision_dynamics_analysis(_dataset())

    assert report["static_mode"]["acceptance_ratio"] == 1.0
    assert report["validation"]["uses_existing_evaluation_runner_decisions"] is True
    assert report["validation"]["metrics_v1_unmodified"] is True
    assert report["validation"]["economic_closure_unmodified"] is True
    assert report["validation"]["new_features_created"] is False
    assert report["validation"]["new_dataset_created"] is False
    assert report["validation"]["optimization_loop_used"] is False


def test_dynamic_mode_scales_decision_score_without_direction_change():
    dynamic_decisions = apply_dynamic_decision_scaling(
        signals=(
            {
                "signal_id": "signal-1",
                "source_event_id": "event-1",
                "volatility_regime": "high",
                "z_score": 2.5,
            },
        ),
        decisions=(
            {
                "decision_id": "decision-1",
                "source_signal_id": "signal-1",
                "decision_score": 2.0,
                "direction": "long",
                "simulation_status": "accepted",
            },
        ),
        micro_features=(
            {
                "event_id": "event-1",
                "micro_v2_corr_to_btc_20": 0.9,
                "micro_v2_btc_eth_corr_20": 0.85,
                "micro_v2_tail_intensity_20": 0.25,
                "micro_v2_rolling_volatility_20": 0.02,
            },
        ),
    )

    assert dynamic_decisions[0]["direction"] == "long"
    assert dynamic_decisions[0]["decision_score"] == 1.08


def test_decision_dynamics_report_contains_required_comparison_fields():
    report = build_decision_dynamics_analysis(_dataset())

    assert set(report["delta"]) == {"edge", "cost_adjusted_pnl", "total_pnl"}
    assert "edge" in report["static_mode"]
    assert "cost_adjusted_pnl" in report["static_mode"]
    assert "edge" in report["dynamic_mode"]
    assert "cost_adjusted_pnl" in report["dynamic_mode"]
    assert report["validation"]["dynamic_direction_changes"] == 0
    assert report["dynamic_mode"]["scaling_summary"]["count"] == report["dataset_rows"]


def test_decision_dynamics_writes_required_artifact(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_dataset(dataset_dir / "candles.csv")

    report = run_decision_dynamics_analysis(dataset_dir, output_dir=tmp_path)

    artifact = tmp_path / SUMMARY_FILENAME
    assert artifact.exists()
    assert report["dataset_rows"] == 144
    assert report["symbols"] == 6


def _dataset():
    rows = []
    for hour in range(24):
        timestamp = f"2024-01-01T{hour:02d}:00:00Z"
        for symbol_index, symbol in enumerate(SYMBOLS, start=1):
            open_price = 100.0 + symbol_index * 10.0 + hour * symbol_index * 0.25
            close_price = open_price * (1.0 + ((-1) ** hour) * symbol_index * 0.001)
            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "open": str(open_price),
                    "high": str(max(open_price, close_price) * 1.002),
                    "low": str(min(open_price, close_price) * 0.998),
                    "close": str(close_price),
                    "volume": str(1000.0 + hour + symbol_index),
                    "simulation_status": "accepted",
                }
            )
    return normalize_dataset(rows)


def _write_dataset(path: Path) -> None:
    rows = _dataset()
    path.write_text(
        "timestamp,symbol,open,high,low,close,volume,simulation_status\n"
        + "\n".join(
            ",".join(
                (
                    str(row["timestamp"]),
                    str(row["symbol"]),
                    str(row["open"]),
                    str(row["high"]),
                    str(row["low"]),
                    str(row["close"]),
                    str(row["volume"]),
                    str(row["simulation_status"]),
                )
            )
            for row in rows
        )
        + "\n",
        encoding="utf-8",
    )
