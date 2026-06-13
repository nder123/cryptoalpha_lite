from __future__ import annotations

from collections.abc import Sequence

DIRECTIONS = ("long", "short")


def generate_random_decisions(
    signals: Sequence[dict[str, object]],
    *,
    seed: int = 0,
) -> tuple[dict[str, object], ...]:
    return tuple(
        _decision(
            index=index,
            signal=signal,
            direction=_deterministic_random_direction(index=index, seed=seed),
        )
        for index, signal in enumerate(signals, start=1)
    )


def generate_naive_momentum(
    signals: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(
        _decision(
            index=index,
            signal=signal,
            direction=_momentum_direction(signal),
        )
        for index, signal in enumerate(signals, start=1)
    )


def _decision(
    *,
    index: int,
    signal: dict[str, object],
    direction: str,
) -> dict[str, object]:
    return {
        "decision_id": f"decision-{index}",
        "source_signal_id": signal["signal_id"],
        "symbol": signal.get("symbol"),
        "timestamp": signal.get("timestamp"),
        "direction": direction,
        "simulation_status": signal["simulation_status"],
    }


def _momentum_direction(signal: dict[str, object]) -> str:
    open_price = _float_value(signal.get("open"))
    close_price = _float_value(signal.get("close"))
    if close_price >= open_price:
        return "long"
    return "short"


def _deterministic_random_direction(*, index: int, seed: int) -> str:
    return DIRECTIONS[((seed + index) * 1103515245 + 12345) % len(DIRECTIONS)]


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0
