from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.dataset_expansion_v1 import (
    REQUIRED_SYMBOLS,
    expand_dataset,
)
from scripts.behavior_validation.economic_closure_runner import (
    run_economic_closure_validation,
)
from scripts.behavior_validation.evaluation_runner import run_historical_evaluation


class StaticKlineSource:
    source_name = "static_test_klines"

    def fetch_month(
        self,
        *,
        symbol: str,
        month: str,
        interval: str,
    ) -> tuple[dict[str, str], ...]:
        base_prices = {
            "BTCUSDT": 42000.0,
            "ETHUSDT": 2300.0,
            "SOLUSDT": 98.0,
            "XRPUSDT": 0.55,
            "DOGEUSDT": 0.081,
            "LINKUSDT": 14.2,
        }
        base_price = base_prices[symbol]
        return tuple(
            _row(
                timestamp=f"2024-01-01T0{index}:00:00Z",
                symbol=symbol,
                open_price=base_price * (1.0 + index * 0.01),
            )
            for index in range(4)
        )


def test_expanded_dataset_covers_required_symbols(tmp_path: Path):
    dataset_dir = tmp_path / "expanded_dataset"
    summary_path = tmp_path / "dataset_summary_v1.json"

    summary = expand_dataset(
        output_dataset_dir=dataset_dir,
        summary_path=summary_path,
        source=StaticKlineSource(),
    )
    rows = normalize_dataset(load_historical_data(dataset_dir))

    assert summary["symbol_count"] == 6
    assert summary["row_count"] == 24
    assert set(summary["symbols"]) == set(REQUIRED_SYMBOLS)
    assert summary["rows_per_symbol"] == {symbol: 4 for symbol in REQUIRED_SYMBOLS}
    assert {row["symbol"] for row in rows} == set(REQUIRED_SYMBOLS)
    assert summary_path.exists()


def test_expanded_dataset_is_pipeline_compatible(tmp_path: Path):
    dataset_dir = tmp_path / "expanded_dataset"
    expand_dataset(
        output_dataset_dir=dataset_dir,
        summary_path=tmp_path / "dataset_summary_v1.json",
        source=StaticKlineSource(),
    )

    evaluation = run_historical_evaluation(dataset_dir, output_dir=tmp_path / "eval")
    closure = run_economic_closure_validation(
        dataset_dir, output_dir=tmp_path / "closure"
    )

    assert evaluation["signals"] == 24
    assert evaluation["decisions"] == 24
    assert evaluation["executions"] == 24
    assert closure.keys() == {
        "total_pnl",
        "regime_pnl",
        "cost_adjusted_pnl",
        "edge_score",
    }


def test_volatility_summary_is_non_empty_per_symbol(tmp_path: Path):
    summary = expand_dataset(
        output_dataset_dir=tmp_path / "expanded_dataset",
        summary_path=tmp_path / "dataset_summary_v1.json",
        source=StaticKlineSource(),
    )

    volatility = summary["volatility_statistics_per_symbol"]

    assert set(volatility) == set(REQUIRED_SYMBOLS)
    for symbol_stats in volatility.values():
        assert symbol_stats["close_to_close_return_stddev"] >= 0.0
        assert symbol_stats["mean_abs_close_to_close_return"] > 0.0
        assert symbol_stats["mean_range_pct"] > 0.0


def _row(
    *,
    timestamp: str,
    symbol: str,
    open_price: float,
) -> dict[str, str]:
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "open": str(open_price),
        "high": str(open_price * 1.01),
        "low": str(open_price * 0.99),
        "close": str(open_price * 1.005),
        "volume": "1000.0",
        "simulation_status": "accepted",
    }
