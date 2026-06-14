from pathlib import Path

from scripts.behavior_validation.data_adapter import normalize_dataset
from scripts.behavior_validation.feature_impact_analysis_v1 import (
    SUMMARY_FILENAME,
    build_feature_impact_analysis,
    run_feature_impact_analysis,
)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT")


def test_feature_impact_analysis_reports_predictive_delta_without_pipeline_change():
    report = build_feature_impact_analysis(_dataset())

    assert (
        report["predictive_delta"]["baseline_edge"]
        == report["predictive_delta"]["expanded_edge"]
    )
    assert report["predictive_delta"]["delta"] == 0.0
    assert report["stability_constraint"]["confirmed"] is True
    assert report["stability_constraint"]["pipeline_behavior_changed"] is False


def test_feature_impact_analysis_reports_information_gain_proxies():
    report = build_feature_impact_analysis(_dataset())
    proxy = report["information_gain_proxy"]

    assert "mutual_information_proxy_change" in proxy
    assert proxy["feature_importance_stability"]["common_feature_count"] > 0
    assert (
        proxy["feature_importance_stability"]["max_abs_common_importance_delta"] == 0.0
    )
    assert proxy["signal_variance_shift"]["delta"] == 0.0


def test_feature_impact_analysis_reports_decision_sensitivity_unchanged():
    report = build_feature_impact_analysis(_dataset())
    sensitivity = report["decision_sensitivity_check"]

    assert sensitivity["decision_output_distribution_changed"] is False
    assert sensitivity["regime_routing_behavior_changed"] is False
    assert sensitivity["execution_acceptance_ratio_changed"] is False
    assert sensitivity["execution_acceptance_ratio_delta"] == 0.0


def test_feature_impact_analysis_writes_required_artifact(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_dataset(dataset_dir / "candles.csv")

    report = run_feature_impact_analysis(dataset_dir, output_dir=tmp_path)

    artifact = tmp_path / SUMMARY_FILENAME
    assert artifact.exists()
    assert report["dataset_rows"] == 144
    assert report["symbols"] == 6


def _dataset():
    rows = []
    for hour in range(24):
        timestamp = f"2024-01-01T{hour:02d}:00:00Z"
        for symbol_index, symbol in enumerate(SYMBOLS, start=1):
            open_price = 100.0 + symbol_index * 10.0 + hour * symbol_index * 0.2
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
