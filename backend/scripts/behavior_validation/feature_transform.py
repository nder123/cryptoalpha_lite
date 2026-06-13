from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from scripts.behavior_validation.edge_validation_runner import _outcomes_by_event_id


def transform_market_features(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    features_by_event_id = {}
    for rows in _rows_by_symbol(data).values():
        ranges: list[float] = []
        deltas: list[float] = []
        closes: list[float] = []
        previous_delta = 0.0
        previous_range = 0.0

        for row in sorted(rows, key=lambda value: str(value["timestamp"])):
            open_price = _float_value(row.get("open"))
            high_price = _float_value(row.get("high"))
            low_price = _float_value(row.get("low"))
            close_price = _float_value(row.get("close"))
            previous_close = closes[-1] if closes else open_price
            close_delta = _ratio(close_price - previous_close, previous_close)
            range_pct = _ratio(high_price - low_price, open_price)

            ranges.append(range_pct)
            deltas.append(close_delta)
            closes.append(close_price)

            local_ranges = tuple(ranges[-3:])
            local_deltas = tuple(deltas[-3:])
            local_closes = tuple(closes[-3:])
            local_range_mean = _mean(local_ranges)
            local_abs_delta_mean = _mean(tuple(abs(value) for value in local_deltas))
            local_close_mean = _mean(local_closes)
            local_close_std = _stddev(local_closes)

            features_by_event_id[str(row["event_id"])] = {
                "event_id": row["event_id"],
                "symbol": row.get("symbol"),
                "timestamp": row.get("timestamp"),
                "volatility_regime": _volatility_regime(
                    range_pct,
                    local_range_mean,
                ),
                "market_structure": _market_structure(local_closes),
                "delta_acceleration": close_delta - previous_delta,
                "volatility_cluster": _ratio(
                    local_range_mean - range_pct,
                    range_pct,
                ),
                "range_behavior": _range_behavior(range_pct, previous_range),
                "range_expansion": _ratio(range_pct - previous_range, previous_range),
                "normalized_deviation": _ratio(
                    close_price - local_close_mean,
                    local_close_mean,
                ),
                "z_score": _ratio(close_price - local_close_mean, local_close_std),
                "relative_strength": _ratio(close_delta, local_abs_delta_mean),
            }
            previous_delta = close_delta
            previous_range = range_pct

    return tuple(
        features_by_event_id[str(row["event_id"])]
        for row in data
        if str(row["event_id"]) in features_by_event_id
    )


def generate_signal_v2(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    features_by_event_id = {
        str(features["event_id"]): features
        for features in transform_market_features(data)
    }
    outcome_by_event_id = _outcomes_by_event_id(data)
    return tuple(
        _signal_v2(
            index=index,
            row=row,
            features=features_by_event_id[str(row["event_id"])],
            outcome=outcome_by_event_id.get(str(row["event_id"])),
        )
        for index, row in enumerate(data, start=1)
    )


def _signal_v2(
    *,
    index: int,
    row: dict[str, object],
    features: dict[str, object],
    outcome: str | None,
) -> dict[str, object]:
    score = _signal_v2_score(features)
    return {
        "signal_id": f"signal-v2-{index}",
        "source_event_id": row["event_id"],
        "symbol": row.get("symbol"),
        "timestamp": row.get("timestamp"),
        "open": row.get("open"),
        "close": row.get("close"),
        "outcome_direction": outcome,
        "volatility_regime": features["volatility_regime"],
        "market_structure": features["market_structure"],
        "delta_acceleration": features["delta_acceleration"],
        "volatility_cluster": features["volatility_cluster"],
        "range_behavior": features["range_behavior"],
        "range_expansion": features["range_expansion"],
        "normalized_deviation": features["normalized_deviation"],
        "z_score": features["z_score"],
        "relative_strength": features["relative_strength"],
        "signal_strength": abs(score),
        "signal_sensitivity": abs(_float_value(features["z_score"])),
        "signal_delta": score,
        "signal_v2_score": score,
        "signal_v2_direction": _direction(score),
        "signal_v2_bucket": _signal_bucket(score, features),
        "simulation_status": row["simulation_status"],
    }


def _signal_v2_score(features: dict[str, object]) -> float:
    return (
        0.35 * _float_value(features.get("relative_strength"))
        + 0.25 * _float_value(features.get("z_score"))
        + 0.2 * _float_value(features.get("delta_acceleration"))
        + 0.1 * _float_value(features.get("range_expansion"))
        + 0.1 * _float_value(features.get("volatility_cluster"))
    )


def _signal_bucket(score: float, features: dict[str, object]) -> str:
    return "|".join(
        (
            _score_bucket(score),
            str(features["volatility_regime"]),
            str(features["market_structure"]),
            str(features["range_behavior"]),
        )
    )


def _score_bucket(score: float) -> str:
    if score <= -0.5:
        return "negative_high"
    if score < 0.0:
        return "negative_low"
    if score < 0.5:
        return "positive_low"
    return "positive_high"


def _direction(score: float) -> str:
    if score >= 0.0:
        return "long"
    return "short"


def _volatility_regime(range_pct: float, local_range_mean: float) -> str:
    if local_range_mean == 0.0:
        return "low"
    if range_pct < 0.8 * local_range_mean:
        return "low"
    if range_pct > 1.2 * local_range_mean:
        return "high"
    return "mid"


def _market_structure(closes: Sequence[float]) -> str:
    if len(closes) < 3:
        return "chop"

    net_move = abs(closes[-1] - closes[0])
    path_move = sum(
        abs(current - previous)
        for previous, current in zip(closes, closes[1:], strict=False)
    )
    if _ratio(net_move, path_move) >= 0.6:
        return "trend"
    return "chop"


def _range_behavior(range_pct: float, previous_range: float) -> str:
    if previous_range == 0.0:
        return "neutral"
    ratio = _ratio(range_pct - previous_range, previous_range)
    if ratio <= -0.2:
        return "compression"
    if ratio >= 0.2:
        return "expansion"
    return "neutral"


def _rows_by_symbol(
    data: Sequence[dict[str, object]],
) -> dict[str, tuple[dict[str, object], ...]]:
    rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in data:
        rows[str(row["symbol"])].append(row)
    return {symbol: tuple(symbol_rows) for symbol, symbol_rows in sorted(rows.items())}


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


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0
