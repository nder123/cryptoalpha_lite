from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)

SUMMARY_FILENAME = "market_state_labeling_v1.json"
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
BTC_SYMBOL = "BTCUSDT"
VOLATILITY_WINDOW = 20
TREND_WINDOW = 10
STRESS_WINDOW = 20
VOLATILITY_SPIKE_RATIO = 1.5
TAIL_RETURN_THRESHOLD = 0.01


def run_market_state_labeling(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    report = build_market_state_labeling_report(data)
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_market_state_labeling_report(
    data: Sequence[dict[str, object]],
) -> dict[str, object]:
    labels = label_market_states(data)
    return {
        "dataset_rows": len(data),
        "symbols": len({str(row["symbol"]) for row in data}),
        "state_labels": labels,
        "state_distribution_per_symbol": _state_distribution_per_symbol(labels),
        "state_transition_counts": _state_transition_counts(labels),
        "entropy_of_state_sequences": _entropy_of_state_sequences(labels),
        "cross_symbol_state_synchronization": _cross_symbol_state_synchronization(
            labels
        ),
        "stability_metric": _stability_metric(labels),
    }


def label_market_states(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    rows_by_symbol = _rows_by_symbol(data)
    returns_by_symbol = _returns_by_symbol(rows_by_symbol)
    volatility_by_event_id = _rolling_volatility_by_event_id(
        rows_by_symbol,
        returns_by_symbol,
    )
    volatility_thresholds = _volatility_thresholds(
        tuple(volatility_by_event_id.values())
    )
    corr_dispersion_by_timestamp = _correlation_dispersion_by_timestamp(
        rows_by_symbol,
        returns_by_symbol,
    )

    labels_by_event_id = {}
    for symbol, rows in rows_by_symbol.items():
        returns = returns_by_symbol[symbol]
        for index, row in enumerate(rows):
            event_id = str(row["event_id"])
            symbol_returns = returns[: index + 1]
            volatility = volatility_by_event_id[event_id]
            state = {
                "volatility": _volatility_state(volatility, volatility_thresholds),
                "trend": _trend_state(rows[: index + 1], symbol_returns),
                "stress": _stress_state(
                    symbol_returns,
                    corr_dispersion_by_timestamp[str(row["timestamp"])],
                ),
            }
            labels_by_event_id[event_id] = {
                "event_id": row["event_id"],
                "symbol": row["symbol"],
                "timestamp": row["timestamp"],
                "state": state,
            }

    return tuple(
        labels_by_event_id[str(row["event_id"])]
        for row in data
        if str(row["event_id"]) in labels_by_event_id
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run market state labeling v1")
    parser.add_argument(
        "historical_data",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_market_state_labeling(
        args.historical_data,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


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


def _returns_by_symbol(
    rows_by_symbol: Mapping[str, Sequence[dict[str, object]]],
) -> dict[str, tuple[float, ...]]:
    returns_by_symbol = {}
    for symbol, rows in rows_by_symbol.items():
        closes = tuple(_float_value(row.get("close")) for row in rows)
        returns_by_symbol[symbol] = tuple(
            0.0 if index == 0 else _ratio(close - closes[index - 1], closes[index - 1])
            for index, close in enumerate(closes)
        )
    return returns_by_symbol


def _rolling_volatility_by_event_id(
    rows_by_symbol: Mapping[str, Sequence[dict[str, object]]],
    returns_by_symbol: Mapping[str, Sequence[float]],
) -> dict[str, float]:
    volatility = {}
    for symbol, rows in rows_by_symbol.items():
        returns = returns_by_symbol[symbol]
        for index, row in enumerate(rows):
            volatility[str(row["event_id"])] = _stddev(
                returns[max(0, index + 1 - VOLATILITY_WINDOW) : index + 1]
            )
    return volatility


def _volatility_thresholds(values: Sequence[float]) -> dict[str, float]:
    return {
        "low_max": _quantile(values, 1.0 / 3.0),
        "mid_max": _quantile(values, 2.0 / 3.0),
    }


def _volatility_state(
    volatility: float,
    thresholds: Mapping[str, float],
) -> str:
    if volatility <= _float_value(thresholds.get("low_max")):
        return "LOW"
    if volatility <= _float_value(thresholds.get("mid_max")):
        return "MID"
    return "HIGH"


def _trend_state(
    rows: Sequence[dict[str, object]],
    returns: Sequence[float],
) -> str:
    window_rows = rows[-TREND_WINDOW:]
    window_returns = returns[-TREND_WINDOW:]
    if len(window_rows) < 2:
        return "FLAT"
    first_close = _float_value(window_rows[0].get("close"))
    last_close = _float_value(window_rows[-1].get("close"))
    slope = _ratio(last_close - first_close, first_close)
    sign_imbalance = _sign_imbalance(window_returns)
    if slope > 0.0 and sign_imbalance >= 0.2:
        return "UP"
    if slope < 0.0 and sign_imbalance <= -0.2:
        return "DOWN"
    return "FLAT"


def _stress_state(
    returns: Sequence[float],
    correlation_dispersion: float,
) -> str:
    short_volatility = _stddev(returns[-5:])
    long_volatility = _stddev(returns[-STRESS_WINDOW:])
    volatility_spike = (
        long_volatility > 0.0
        and _ratio(short_volatility, long_volatility) >= VOLATILITY_SPIKE_RATIO
    )
    tail_intensity = _tail_intensity(returns[-STRESS_WINDOW:])
    if (
        (volatility_spike and correlation_dispersion >= 0.25)
        or tail_intensity >= 0.2
        or correlation_dispersion >= 0.35
    ):
        return "CHAOTIC"
    if volatility_spike or tail_intensity >= 0.1 or correlation_dispersion >= 0.2:
        return "TRANSITIONAL"
    return "STABLE"


def _correlation_dispersion_by_timestamp(
    rows_by_symbol: Mapping[str, Sequence[dict[str, object]]],
    returns_by_symbol: Mapping[str, Sequence[float]],
) -> dict[str, float]:
    returns_by_timestamp = _returns_by_timestamp(rows_by_symbol, returns_by_symbol)
    correlations_by_timestamp = {}
    for timestamp, returns_at_timestamp in returns_by_timestamp.items():
        alt_symbols = tuple(
            symbol for symbol in returns_at_timestamp if symbol != BTC_SYMBOL
        )
        correlations = tuple(
            _rolling_pair_correlation(
                returns_by_timestamp,
                symbol,
                BTC_SYMBOL,
                timestamp,
                STRESS_WINDOW,
            )
            for symbol in alt_symbols
        )
        correlations_by_timestamp[timestamp] = _stddev(correlations)
    return correlations_by_timestamp


def _returns_by_timestamp(
    rows_by_symbol: Mapping[str, Sequence[dict[str, object]]],
    returns_by_symbol: Mapping[str, Sequence[float]],
) -> dict[str, dict[str, float]]:
    by_timestamp: dict[str, dict[str, float]] = defaultdict(dict)
    for symbol, rows in rows_by_symbol.items():
        for row, return_value in zip(rows, returns_by_symbol[symbol], strict=True):
            by_timestamp[str(row["timestamp"])][symbol] = return_value
    return dict(sorted(by_timestamp.items()))


def _rolling_pair_correlation(
    returns_by_timestamp: Mapping[str, Mapping[str, float]],
    symbol: str,
    anchor_symbol: str,
    timestamp: str,
    window: int,
) -> float:
    timestamps = tuple(returns_by_timestamp)
    if timestamp not in returns_by_timestamp:
        return 0.0
    end = timestamps.index(timestamp) + 1
    window_timestamps = timestamps[max(0, end - window) : end]
    pairs = tuple(
        (
            returns_by_timestamp[item][symbol],
            returns_by_timestamp[item][anchor_symbol],
        )
        for item in window_timestamps
        if symbol in returns_by_timestamp[item]
        and anchor_symbol in returns_by_timestamp[item]
    )
    return _correlation(
        tuple(pair[0] for pair in pairs),
        tuple(pair[1] for pair in pairs),
    )


def _state_distribution_per_symbol(
    labels: Sequence[dict[str, object]],
) -> dict[str, dict[str, dict[str, int]]]:
    distributions: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {
            "volatility": Counter(),
            "trend": Counter(),
            "stress": Counter(),
            "combined": Counter(),
        }
    )
    for label in labels:
        symbol = str(label["symbol"])
        state = _state(label)
        distributions[symbol]["volatility"][state["volatility"]] += 1
        distributions[symbol]["trend"][state["trend"]] += 1
        distributions[symbol]["stress"][state["stress"]] += 1
        distributions[symbol]["combined"][_state_key(state)] += 1
    return {
        symbol: {
            dimension: dict(sorted(counter.items()))
            for dimension, counter in dimension_counts.items()
        }
        for symbol, dimension_counts in sorted(distributions.items())
    }


def _state_transition_counts(
    labels: Sequence[dict[str, object]],
) -> dict[str, dict[str, int]]:
    labels_by_symbol = _labels_by_symbol(labels)
    transitions = {}
    for symbol, symbol_labels in labels_by_symbol.items():
        counter: Counter[str] = Counter()
        for previous, current in zip(symbol_labels, symbol_labels[1:], strict=False):
            counter[
                f"{_state_key(_state(previous))}->{_state_key(_state(current))}"
            ] += 1
        transitions[symbol] = dict(sorted(counter.items()))
    return transitions


def _entropy_of_state_sequences(
    labels: Sequence[dict[str, object]],
) -> dict[str, dict[str, float]]:
    entropy_by_symbol = {}
    for symbol, symbol_labels in _labels_by_symbol(labels).items():
        entropy_by_symbol[symbol] = {
            "combined": _entropy(
                tuple(_state_key(_state(label)) for label in symbol_labels)
            ),
            "volatility": _entropy(
                tuple(_state(label)["volatility"] for label in symbol_labels)
            ),
            "trend": _entropy(tuple(_state(label)["trend"] for label in symbol_labels)),
            "stress": _entropy(
                tuple(_state(label)["stress"] for label in symbol_labels)
            ),
        }
    return entropy_by_symbol


def _cross_symbol_state_synchronization(
    labels: Sequence[dict[str, object]],
) -> dict[str, object]:
    labels_by_symbol_timestamp = {
        (str(label["symbol"]), str(label["timestamp"])): label for label in labels
    }
    btc_labels = tuple(label for label in labels if str(label["symbol"]) == BTC_SYMBOL)
    synchronization: dict[str, object] = {}
    aggregate_matches: list[float] = []
    for symbol in sorted({str(label["symbol"]) for label in labels} - {BTC_SYMBOL}):
        paired = tuple(
            (
                btc_label,
                labels_by_symbol_timestamp[(symbol, str(btc_label["timestamp"]))],
            )
            for btc_label in btc_labels
            if (symbol, str(btc_label["timestamp"])) in labels_by_symbol_timestamp
        )
        symbol_sync = {
            "paired_windows": len(paired),
            "combined_match_rate": _match_rate(
                tuple(_state_key(_state(first)) for first, _ in paired),
                tuple(_state_key(_state(second)) for _, second in paired),
            ),
            "volatility_match_rate": _match_rate(
                tuple(_state(first)["volatility"] for first, _ in paired),
                tuple(_state(second)["volatility"] for _, second in paired),
            ),
            "trend_match_rate": _match_rate(
                tuple(_state(first)["trend"] for first, _ in paired),
                tuple(_state(second)["trend"] for _, second in paired),
            ),
            "stress_match_rate": _match_rate(
                tuple(_state(first)["stress"] for first, _ in paired),
                tuple(_state(second)["stress"] for _, second in paired),
            ),
        }
        synchronization[symbol] = symbol_sync
        aggregate_matches.append(symbol_sync["combined_match_rate"])
    synchronization["aggregate"] = {
        "mean_combined_match_rate": _mean(tuple(aggregate_matches)),
        "alt_symbol_count": len(aggregate_matches),
    }
    return synchronization


def _stability_metric(labels: Sequence[dict[str, object]]) -> dict[str, object]:
    labels_by_symbol = _labels_by_symbol(labels)
    transition_rates: list[float] = []
    unique_states: set[str] = set()
    for symbol_labels in labels_by_symbol.values():
        state_keys = tuple(_state_key(_state(label)) for label in symbol_labels)
        unique_states.update(state_keys)
        transition_count = sum(
            1
            for previous, current in zip(state_keys, state_keys[1:], strict=False)
            if previous != current
        )
        denominator = max(1, len(state_keys) - 1)
        transition_rates.append(transition_count / denominator)
    mean_transition_rate = _mean(tuple(transition_rates))
    aggregate_entropy = _entropy(tuple(_state_key(_state(label)) for label in labels))
    return {
        "mean_transition_rate": mean_transition_rate,
        "stability_score": 1.0 - mean_transition_rate,
        "aggregate_entropy": aggregate_entropy,
        "unique_combined_states": len(unique_states),
        "non_degenerate": len(unique_states) > 1 and aggregate_entropy > 0.0,
    }


def _labels_by_symbol(
    labels: Sequence[dict[str, object]],
) -> dict[str, tuple[dict[str, object], ...]]:
    by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
    for label in labels:
        by_symbol[str(label["symbol"])].append(label)
    return {
        symbol: tuple(sorted(symbol_labels, key=lambda label: str(label["timestamp"])))
        for symbol, symbol_labels in sorted(by_symbol.items())
    }


def _state(label: Mapping[str, object]) -> dict[str, str]:
    state = label["state"]
    if not isinstance(state, dict):
        return {"volatility": "LOW", "trend": "FLAT", "stress": "STABLE"}
    return {
        "volatility": str(state["volatility"]),
        "trend": str(state["trend"]),
        "stress": str(state["stress"]),
    }


def _state_key(state: Mapping[str, str]) -> str:
    return "|".join((state["volatility"], state["trend"], state["stress"]))


def _match_rate(first: Sequence[str], second: Sequence[str]) -> float:
    if len(first) != len(second) or not first:
        return 0.0
    matches = sum(
        1
        for first_value, second_value in zip(first, second, strict=True)
        if first_value == second_value
    )
    return matches / len(first)


def _entropy(values: Sequence[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def _quantile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    sorted_values = tuple(sorted(values))
    index = min(
        len(sorted_values) - 1, max(0, int((len(sorted_values) - 1) * quantile))
    )
    return sorted_values[index]


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


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _sign_imbalance(values: Sequence[float]) -> float:
    signs = tuple(_sign(value) for value in values if value != 0.0)
    if not signs:
        return 0.0
    return sum(signs) / len(signs)


def _tail_intensity(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if abs(value) > TAIL_RETURN_THRESHOLD) / len(
        values
    )


def _sign(value: float) -> int:
    if value > 0.0:
        return 1
    if value < 0.0:
        return -1
    return 0


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


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
