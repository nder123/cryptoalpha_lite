from scripts.behavior_validation.data_adapter import normalize_dataset
from scripts.behavior_validation.evaluation_runner import run_evaluation
from scripts.behavior_validation.feature_transform_microstructure_v2 import (
    enrich_dataset_with_microstructure_features,
    transform_microstructure_features_v2,
)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT")
FORBIDDEN_DECISION_KEYS = {
    "signal_strength",
    "signal_sensitivity",
    "signal_delta",
    "regime_component",
    "microstructure_component",
    "relative_component",
    "signal_v2_score",
    "decision_score",
    "direction",
}


def test_microstructure_feature_generation_is_deterministic():
    data = _dataset()

    first = transform_microstructure_features_v2(data)
    second = transform_microstructure_features_v2(data)

    assert first == second


def test_microstructure_feature_shape_is_consistent_across_symbols():
    features = transform_microstructure_features_v2(_dataset())
    keys_by_symbol = {}

    for symbol in SYMBOLS:
        symbol_features = tuple(
            feature for feature in features if feature["symbol"] == symbol
        )
        keys_by_symbol[symbol] = set(symbol_features[0])
        assert len(symbol_features) == 24

    assert len({tuple(sorted(keys)) for keys in keys_by_symbol.values()}) == 1


def test_microstructure_features_do_not_leak_into_decision_layer(tmp_path):
    data = _dataset()
    enriched_data = enrich_dataset_with_microstructure_features(data)
    feature_keys = {
        key for row in enriched_data for key in row if key.startswith("micro_v2_")
    }

    assert feature_keys
    assert feature_keys.isdisjoint(FORBIDDEN_DECISION_KEYS)
    assert run_evaluation(data=data, output_dir=tmp_path / "base") == run_evaluation(
        data=enriched_data,
        output_dir=tmp_path / "enriched",
    )


def test_microstructure_enriched_dataset_keeps_evaluation_input_schema(tmp_path):
    enriched_data = enrich_dataset_with_microstructure_features(_dataset())
    required_keys = {
        "event_id",
        "row_number",
        "timestamp",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "simulation_status",
    }

    assert all(required_keys.issubset(row) for row in enriched_data)
    report = run_evaluation(data=enriched_data, output_dir=tmp_path)
    assert report["signals"] == len(enriched_data)
    assert report["decisions"] == len(enriched_data)
    assert report["executions"] == len(enriched_data)


def _dataset():
    rows = []
    for hour in range(24):
        timestamp = f"2024-01-01T{hour:02d}:00:00Z"
        for symbol_index, symbol in enumerate(SYMBOLS, start=1):
            open_price = 100.0 + symbol_index * 10.0 + hour * symbol_index * 0.1
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
