from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def build_metrics_v1(
    *,
    signals: Sequence[dict[str, object]],
    decisions: Sequence[dict[str, object]],
    executions: Sequence[dict[str, object]],
    processing_failures: int = 0,
) -> dict[str, object]:
    windows = _windows(signals)
    signals_generated = len(signals)
    decisions_generated = len(decisions)
    executions_attempted = len(decisions)
    executions_accepted = _count_execution_status(executions, "accepted")
    executions_rejected = _count_execution_status(executions, "rejected")

    return {
        "signals_generated": signals_generated,
        "signals_per_symbol": _signals_per_symbol(signals),
        "signals_per_window": _signals_per_window(signals),
        "decisions_generated": decisions_generated,
        "decision_rate": _ratio(decisions_generated, signals_generated),
        "decision_density": _ratio(decisions_generated, len(windows)),
        "executions_attempted": executions_attempted,
        "executions_accepted": executions_accepted,
        "executions_rejected": executions_rejected,
        "acceptance_ratio": _ratio(executions_accepted, executions_attempted),
        "empty_windows": 0,
        "missing_data_windows": _missing_data_windows(signals),
        "processing_failures": processing_failures,
    }


def _signals_per_symbol(signals: Sequence[dict[str, object]]) -> dict[str, int]:
    counts = Counter(
        str(signal["symbol"]) for signal in signals if signal.get("symbol") is not None
    )
    return dict(sorted(counts.items()))


def _signals_per_window(signals: Sequence[dict[str, object]]) -> dict[str, int]:
    counts = Counter(_window(signal) for signal in signals)
    return dict(sorted(counts.items()))


def _windows(signals: Sequence[dict[str, object]]) -> tuple[str, ...]:
    return tuple(sorted({_window(signal) for signal in signals}))


def _window(signal: dict[str, object]) -> str:
    timestamp = signal.get("timestamp")
    if timestamp is None:
        return "missing"
    return str(timestamp)


def _count_execution_status(
    executions: Sequence[dict[str, object]],
    status: str,
) -> int:
    return sum(1 for execution in executions if execution["status"] == status)


def _missing_data_windows(signals: Sequence[dict[str, object]]) -> int:
    return sum(1 for signal in signals if signal.get("timestamp") is None)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
