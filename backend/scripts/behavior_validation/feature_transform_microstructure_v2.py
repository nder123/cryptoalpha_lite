from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.evaluation_runner import run_evaluation
from scripts.behavior_validation.feature_transform import _volatility_regime

ROLLING_WINDOWS = (5, 10, 20)
AUTOCORR_LAGS = (1, 2, 3)
TAIL_RETURN_THRESHOLD = 0.01
BTC_SYMBOL = "BTCUSDT"
ETH_SYMBOL = "ETHUSDT"
ALT_SYMBOLS = ("SOLUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT")
SUMMARY_FILENAME = "microstructure_features_v2_summary.json"
BASE_ROW_KEYS = (
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
)


def transform_microstructure_features_v2(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    returns_by_symbol = _returns_by_symbol(data)
    returns_by_timestamp = _returns_by_timestamp(data, returns_by_symbol)
    btc_eth_corr_by_timestamp = _btc_eth_correlation_by_timestamp(returns_by_timestamp)

    features_by_event_id: dict[str, dict[str, object]] = {}
    for symbol, rows in _rows_by_symbol(data).items():
        returns = returns_by_symbol[symbol]
        for index, row in enumerate(rows):
            symbol_returns = returns[: index + 1]
            volatility_20 = _stddev(symbol_returns[-20:])
            return_acceleration = _return_acceleration(returns, index)
            btc_corr = _rolling_pair_correlation(
                returns_by_timestamp=returns_by_timestamp,
                symbol=symbol,
                anchor_symbol=BTC_SYMBOL,
                timestamp=str(row["timestamp"]),
                window=20,
            )
            features_by_event_id[str(row["event_id"])] = {
                "event_id": row["event_id"],
                "symbol": row.get("symbol"),
                "timestamp": row.get("timestamp"),
                "micro_v2_rolling_volatility_5": _stddev(symbol_returns[-5:]),
                "micro_v2_rolling_volatility_10": _stddev(symbol_returns[-10:]),
                "micro_v2_rolling_volatility_20": volatility_20,
                "micro_v2_abs_return_autocorr_lag_1": _autocorrelation(
                    tuple(abs(value) for value in symbol_returns[-20:]),
                    lag=1,
                ),
                "micro_v2_abs_return_autocorr_lag_2": _autocorrelation(
                    tuple(abs(value) for value in symbol_returns[-20:]),
                    lag=2,
                ),
                "micro_v2_abs_return_autocorr_lag_3": _autocorrelation(
                    tuple(abs(value) for value in symbol_returns[-20:]),
                    lag=3,
                ),
                "micro_v2_return_acceleration": return_acceleration,
                "micro_v2_directional_persistence_20": _directional_persistence(
                    symbol_returns[-20:]
                ),
                "micro_v2_btc_eth_corr_20": btc_eth_corr_by_timestamp[
                    str(row["timestamp"])
                ],
                "micro_v2_corr_to_btc_20": btc_corr,
                "micro_v2_beta_to_btc_20": _rolling_beta_to_btc(
                    returns_by_timestamp=returns_by_timestamp,
                    symbol=symbol,
                    timestamp=str(row["timestamp"]),
                    window=20,
                ),
                "micro_v2_skewness_sign_imbalance_20": _sign_imbalance(
                    symbol_returns[-20:]
                ),
                "micro_v2_tail_intensity_20": _tail_intensity(symbol_returns[-20:]),
                "micro_v2_volatility_regime": _micro_volatility_regime(
                    row, volatility_20
                ),
                "micro_v2_vol_momentum_interaction": volatility_20
                * return_acceleration,
                "micro_v2_vol_correlation_interaction": volatility_20 * btc_corr,
            }

    return tuple(
        features_by_event_id[str(row["event_id"])]
        for row in data
        if str(row["event_id"]) in features_by_event_id
    )


def enrich_dataset_with_microstructure_features(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    features_by_event_id = {
        str(features["event_id"]): features
        for features in transform_microstructure_features_v2(data)
    }
    return tuple(
        {
            **row,
            **{
                key: value
                for key, value in features_by_event_id[str(row["event_id"])].items()
                if key not in BASE_ROW_KEYS
            },
        }
        for row in data
    )


def build_microstructure_features_v2_summary(
    data: Sequence[dict[str, object]],
    *,
    compatibility_output_dir: Path | None = None,
) -> dict[str, object]:
    features = transform_microstructure_features_v2(data)
    enriched_data = enrich_dataset_with_microstructure_features(data)
    compatibility_dir = compatibility_output_dir or (
        Path.home() / "behavior_validation_outputs" / "microstructure_v2_compatibility"
    )
    base_report = run_evaluation(data=data, output_dir=compatibility_dir)
    enriched_report = run_evaluation(
        data=enriched_data,
        output_dir=compatibility_dir,
    )
    return {
        "feature_count_per_symbol": _feature_count_per_symbol(features),
        "correlation_summary": _correlation_summary(features),
        "volatility_feature_stats": _volatility_feature_stats(features),
        "missing_nan_diagnostics": _missing_nan_diagnostics(features),
        "dataset_compatibility_check": {
            "compatible": _compatible_reports(base_report, enriched_report),
            "rows": len(data),
            "features": len(features),
            "signals_unchanged": base_report["signals"] == enriched_report["signals"],
            "decisions_unchanged": base_report["decisions"]
            == enriched_report["decisions"],
            "executions_unchanged": base_report["executions"]
            == enriched_report["executions"],
        },
    }


def write_microstructure_features_v2_summary(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    target_output_dir = output_dir or _default_output_dir()
    data = normalize_dataset(load_historical_data(dataset_path))
    summary = build_microstructure_features_v2_summary(data)
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build microstructure features v2")
    parser.add_argument(
        "historical_data",
        nargs="?",
        type=Path,
        default=_default_output_dir() / "expanded_dataset_v1",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    summary = write_microstructure_features_v2_summary(
        args.historical_data,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


def _returns_by_symbol(
    data: Sequence[dict[str, object]],
) -> dict[str, tuple[float, ...]]:
    returns_by_symbol = {}
    for symbol, rows in _rows_by_symbol(data).items():
        returns = []
        previous_close = _float_value(rows[0].get("open")) if rows else 0.0
        for row in rows:
            close_price = _float_value(row.get("close"))
            returns.append(_ratio(close_price - previous_close, previous_close))
            previous_close = close_price
        returns_by_symbol[symbol] = tuple(returns)
    return returns_by_symbol


def _returns_by_timestamp(
    data: Sequence[dict[str, object]],
    returns_by_symbol: Mapping[str, Sequence[float]],
) -> dict[str, dict[str, float]]:
    rows_by_symbol = _rows_by_symbol(data)
    by_timestamp: dict[str, dict[str, float]] = defaultdict(dict)
    for symbol, rows in rows_by_symbol.items():
        returns = returns_by_symbol[symbol]
        for row, return_value in zip(rows, returns, strict=True):
            by_timestamp[str(row["timestamp"])][symbol] = return_value
    return dict(sorted(by_timestamp.items()))


def _btc_eth_correlation_by_timestamp(
    returns_by_timestamp: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    correlations = {}
    for timestamp in returns_by_timestamp:
        correlations[timestamp] = _rolling_pair_correlation(
            returns_by_timestamp=returns_by_timestamp,
            symbol=BTC_SYMBOL,
            anchor_symbol=ETH_SYMBOL,
            timestamp=timestamp,
            window=20,
        )
    return correlations


def _rolling_pair_correlation(
    *,
    returns_by_timestamp: Mapping[str, Mapping[str, float]],
    symbol: str,
    anchor_symbol: str,
    timestamp: str,
    window: int,
) -> float:
    paired = _rolling_pairs(
        returns_by_timestamp=returns_by_timestamp,
        symbol=symbol,
        anchor_symbol=anchor_symbol,
        timestamp=timestamp,
        window=window,
    )
    return _correlation(
        tuple(pair[0] for pair in paired),
        tuple(pair[1] for pair in paired),
    )


def _rolling_beta_to_btc(
    *,
    returns_by_timestamp: Mapping[str, Mapping[str, float]],
    symbol: str,
    timestamp: str,
    window: int,
) -> float:
    if symbol == BTC_SYMBOL:
        return 1.0
    paired = _rolling_pairs(
        returns_by_timestamp=returns_by_timestamp,
        symbol=symbol,
        anchor_symbol=BTC_SYMBOL,
        timestamp=timestamp,
        window=window,
    )
    symbol_returns = tuple(pair[0] for pair in paired)
    btc_returns = tuple(pair[1] for pair in paired)
    btc_variance = _variance(btc_returns)
    if btc_variance == 0.0:
        return 0.0
    return _covariance(symbol_returns, btc_returns) / btc_variance


def _rolling_pairs(
    *,
    returns_by_timestamp: Mapping[str, Mapping[str, float]],
    symbol: str,
    anchor_symbol: str,
    timestamp: str,
    window: int,
) -> tuple[tuple[float, float], ...]:
    timestamps = tuple(returns_by_timestamp)
    if timestamp not in returns_by_timestamp:
        return ()
    end = timestamps.index(timestamp) + 1
    window_timestamps = timestamps[max(0, end - window) : end]
    return tuple(
        (
            returns_by_timestamp[item][symbol],
            returns_by_timestamp[item][anchor_symbol],
        )
        for item in window_timestamps
        if symbol in returns_by_timestamp[item]
        and anchor_symbol in returns_by_timestamp[item]
    )


def _return_acceleration(returns: Sequence[float], index: int) -> float:
    if index == 0:
        return 0.0
    return returns[index] - returns[index - 1]


def _directional_persistence(values: Sequence[float]) -> float:
    signs = tuple(_sign(value) for value in values if value != 0.0)
    if len(signs) < 2:
        return 0.0
    consistent = sum(
        1
        for previous, current in zip(signs, signs[1:], strict=False)
        if previous == current
    )
    return consistent / (len(signs) - 1)


def _sign_imbalance(values: Sequence[float]) -> float:
    signs = tuple(_sign(value) for value in values if value != 0.0)
    if not signs:
        return 0.0
    return sum(signs) / len(signs)


def _tail_intensity(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    tail_count = sum(1 for value in values if abs(value) > TAIL_RETURN_THRESHOLD)
    return tail_count / len(values)


def _micro_volatility_regime(row: Mapping[str, object], volatility_20: float) -> str:
    range_pct = _ratio(
        _float_value(row.get("high")) - _float_value(row.get("low")),
        _float_value(row.get("open")),
    )
    return _volatility_regime(range_pct, volatility_20)


def _rows_by_symbol(
    data: Sequence[dict[str, object]],
) -> dict[str, tuple[dict[str, object], ...]]:
    rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in data:
        rows[str(row["symbol"])].append(row)
    return {
        symbol: tuple(sorted(symbol_rows, key=lambda row: str(row["timestamp"])))
        for symbol, symbol_rows in sorted(rows.items())
    }


def _feature_count_per_symbol(
    features: Sequence[dict[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for feature in features:
        counts[str(feature["symbol"])] += 1
    return dict(sorted(counts.items()))


def _correlation_summary(
    features: Sequence[dict[str, object]],
) -> dict[str, dict[str, float]]:
    btc_corr_values = tuple(
        _float_value(feature.get("micro_v2_btc_eth_corr_20")) for feature in features
    )
    summary = {"BTC_ETH": _stats(btc_corr_values)}
    for symbol in ALT_SYMBOLS:
        beta_values = tuple(
            _float_value(feature.get("micro_v2_beta_to_btc_20"))
            for feature in features
            if feature.get("symbol") == symbol
        )
        corr_values = tuple(
            _float_value(feature.get("micro_v2_corr_to_btc_20"))
            for feature in features
            if feature.get("symbol") == symbol
        )
        summary[f"{symbol}_beta_to_BTC"] = _stats(beta_values)
        summary[f"{symbol}_corr_to_BTC"] = _stats(corr_values)
    return summary


def _volatility_feature_stats(
    features: Sequence[dict[str, object]],
) -> dict[str, dict[str, float]]:
    stats = {}
    for symbol in sorted({str(feature["symbol"]) for feature in features}):
        symbol_features = tuple(
            feature for feature in features if feature.get("symbol") == symbol
        )
        for window in ROLLING_WINDOWS:
            key = f"micro_v2_rolling_volatility_{window}"
            stats[f"{symbol}_{key}"] = _stats(
                tuple(_float_value(feature.get(key)) for feature in symbol_features)
            )
    return stats


def _missing_nan_diagnostics(
    features: Sequence[dict[str, object]],
) -> dict[str, object]:
    feature_keys = sorted(
        {key for feature in features for key in feature if key.startswith("micro_v2_")}
    )
    missing_by_feature = {
        key: sum(1 for feature in features if key not in feature)
        for key in feature_keys
    }
    nan_by_feature = {
        key: sum(1 for feature in features if _is_nan(feature.get(key)))
        for key in feature_keys
    }
    return {
        "feature_keys": feature_keys,
        "missing_by_feature": missing_by_feature,
        "nan_by_feature": nan_by_feature,
        "total_missing": sum(missing_by_feature.values()),
        "total_nan": sum(nan_by_feature.values()),
    }


def _compatible_reports(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> bool:
    return (
        first.get("signals") == second.get("signals")
        and first.get("decisions") == second.get("decisions")
        and first.get("executions") == second.get("executions")
        and first.get("metrics") == second.get("metrics")
        and first.get("metrics_v1") == second.get("metrics_v1")
    )


def _autocorrelation(values: Sequence[float], *, lag: int) -> float:
    if len(values) <= lag:
        return 0.0
    return _correlation(tuple(values[lag:]), tuple(values[:-lag]))


def _correlation(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != len(second) or len(first) < 2:
        return 0.0
    first_std = _stddev(first)
    second_std = _stddev(second)
    if first_std == 0.0 or second_std == 0.0:
        return 0.0
    return _covariance(first, second) / (first_std * second_std)


def _covariance(first: Sequence[float], second: Sequence[float]) -> float:
    if len(first) != len(second) or not first:
        return 0.0
    first_mean = _mean(first)
    second_mean = _mean(second)
    return _mean(
        tuple(
            (first_value - first_mean) * (second_value - second_mean)
            for first_value, second_value in zip(first, second, strict=True)
        )
    )


def _variance(values: Sequence[float]) -> float:
    stddev = _stddev(values)
    return stddev * stddev


def _stats(values: Sequence[float]) -> dict[str, float]:
    return {
        "min": min(values, default=0.0),
        "max": max(values, default=0.0),
        "mean": _mean(values),
        "stddev": _stddev(values),
    }


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _sign(value: float) -> int:
    if value > 0.0:
        return 1
    return -1


def _is_nan(value: object) -> bool:
    return isinstance(value, float) and math.isnan(value)


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
