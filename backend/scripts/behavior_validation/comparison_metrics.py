from __future__ import annotations

import math
from collections.abc import Sequence


def build_comparison_metrics(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    executions: Sequence[dict[str, object]],
    metrics_v1: dict[str, object],
) -> dict[str, float]:
    signal_by_id = {str(signal["signal_id"]): signal for signal in signals}
    directions = tuple(_direction(decision) for decision in decisions)

    return {
        "hit_rate": _hit_rate(signal_by_id, decisions),
        "directional_consistency": _directional_consistency(directions),
        "stability_score": _stability_score(metrics_v1),
        "execution_acceptance_ratio": _execution_acceptance_ratio(
            executions,
            metrics_v1,
        ),
    }


def _hit_rate(
    signal_by_id: dict[str, dict[str, object]],
    decisions: Sequence[dict[str, object]],
) -> float:
    comparable = 0
    hits = 0

    for decision in decisions:
        signal = signal_by_id.get(str(decision.get("source_signal_id")))
        if signal is None:
            continue

        direction = _direction(decision)
        outcome_direction = _direction(signal, key="outcome_direction")
        if direction is None or outcome_direction is None:
            continue

        comparable += 1
        if direction == outcome_direction:
            hits += 1

    return _ratio(hits, comparable)


def _directional_consistency(directions: Sequence[str | None]) -> float:
    clean_directions = tuple(
        direction for direction in directions if direction is not None
    )
    if len(clean_directions) < 2:
        return 0.0

    consistent = sum(
        1
        for previous, current in zip(
            clean_directions,
            clean_directions[1:],
            strict=False,
        )
        if previous == current
    )
    return _ratio(consistent, len(clean_directions) - 1)


def _stability_score(metrics_v1: dict[str, object]) -> float:
    total_windows = len(_dict_metric(metrics_v1, "signals_per_window"))
    if total_windows == 0:
        return 0.0

    empty_windows = _int_metric(metrics_v1, "empty_windows")
    missing_data_windows = _int_metric(metrics_v1, "missing_data_windows")
    processing_failures = _int_metric(metrics_v1, "processing_failures")
    unstable_windows = empty_windows + missing_data_windows + processing_failures
    return max(0.0, 1.0 - _ratio(unstable_windows, total_windows))


def _execution_acceptance_ratio(
    executions: Sequence[dict[str, object]],
    metrics_v1: dict[str, object],
) -> float:
    if executions:
        return _float_metric(metrics_v1, "acceptance_ratio")
    return 0.0


def _direction(
    payload: dict[str, object],
    *,
    key: str = "direction",
) -> str | None:
    direction = payload.get(key)
    if direction in {"long", "short"}:
        return str(direction)
    return None


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    value = numerator / denominator
    if math.isnan(value):
        return 0.0
    return value


def _int_metric(metrics: dict[str, object], key: str) -> int:
    value = metrics.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _float_metric(metrics: dict[str, object], key: str) -> float:
    value = metrics.get(key, 0.0)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _dict_metric(metrics: dict[str, object], key: str) -> dict[str, object]:
    value = metrics.get(key, {})
    if isinstance(value, dict):
        return value
    return {}
