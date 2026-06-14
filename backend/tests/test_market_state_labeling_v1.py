from pathlib import Path

from scripts.behavior_validation.data_adapter import normalize_dataset
from scripts.behavior_validation.market_state_labeling_v1 import (
    SUMMARY_FILENAME,
    build_market_state_labeling_report,
    label_market_states,
    run_market_state_labeling,
)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT")
FORBIDDEN_REPORT_KEYS = {
    "edge",
    "pnl",
    "cost_adjusted_pnl",
    "decision_score",
    "execution",
}


def test_market_state_labeling_is_deterministic_and_reproducible():
    data = _dataset()

    first = build_market_state_labeling_report(data)
    second = build_market_state_labeling_report(data)

    assert first == second


def test_market_state_labeling_has_no_decision_or_metric_leakage():
    report = build_market_state_labeling_report(_dataset())
    serialized = str(report)

    for forbidden_key in FORBIDDEN_REPORT_KEYS:
        assert forbidden_key not in serialized
    assert report["stability_metric"]["non_degenerate"] is True


def test_market_state_labeling_assigns_consistent_state_for_identical_inputs():
    labels = label_market_states(_constant_dataset())
    states_by_symbol = {}

    for symbol in SYMBOLS:
        symbol_states = {
            str(label["state"]) for label in labels if str(label["symbol"]) == symbol
        }
        states_by_symbol[symbol] = symbol_states

    assert all(len(states) == 1 for states in states_by_symbol.values())


def test_market_state_labeling_writes_required_artifact(tmp_path):
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_dataset(dataset_dir / "candles.csv")

    report = run_market_state_labeling(dataset_dir, output_dir=tmp_path)

    artifact = tmp_path / SUMMARY_FILENAME
    assert artifact.exists()
    assert report["dataset_rows"] == 144
    assert report["symbols"] == 6
    assert len(report["state_labels"]) == 144
    assert "BTCUSDT" in report["state_distribution_per_symbol"]
    assert "BTCUSDT" in report["state_transition_counts"]
    assert "BTCUSDT" in report["entropy_of_state_sequences"]
    assert "aggregate" in report["cross_symbol_state_synchronization"]


def _dataset():
    rows = []
    for hour in range(24):
        timestamp = f"2024-01-01T{hour:02d}:00:00Z"
        for symbol_index, symbol in enumerate(SYMBOLS, start=1):
            trend_component = hour * symbol_index * 0.25
            shock = 1.0 + ((-1) ** hour) * symbol_index * 0.001
            if hour in {7, 8, 18}:
                shock += symbol_index * 0.002
            open_price = 100.0 + symbol_index * 10.0 + trend_component
            close_price = open_price * shock
            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "open": str(open_price),
                    "high": str(max(open_price, close_price) * 1.003),
                    "low": str(min(open_price, close_price) * 0.997),
                    "close": str(close_price),
                    "volume": str(1000.0 + hour + symbol_index),
                    "simulation_status": "accepted",
                }
            )
    return normalize_dataset(rows)


def _constant_dataset():
    rows = []
    for hour in range(24):
        timestamp = f"2024-01-01T{hour:02d}:00:00Z"
        for symbol_index, symbol in enumerate(SYMBOLS, start=1):
            price = 100.0 + symbol_index
            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "open": str(price),
                    "high": str(price),
                    "low": str(price),
                    "close": str(price),
                    "volume": "1000.0",
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
