from __future__ import annotations


def build_insights_v1(metrics_v1: dict[str, object]) -> dict[str, object]:
    signals_generated = _int_metric(metrics_v1, "signals_generated")
    decisions_generated = _int_metric(metrics_v1, "decisions_generated")
    executions_attempted = _int_metric(metrics_v1, "executions_attempted")
    executions_rejected = _int_metric(metrics_v1, "executions_rejected")
    empty_windows = _int_metric(metrics_v1, "empty_windows")
    processing_failures = _int_metric(metrics_v1, "processing_failures")
    total_windows = len(_dict_metric(metrics_v1, "signals_per_window"))

    decision_efficiency = _ratio(decisions_generated, signals_generated)
    execution_friction = _ratio(executions_rejected, executions_attempted)
    stability_index = _stability_index(
        empty_windows=empty_windows,
        processing_failures=processing_failures,
        total_windows=total_windows,
    )

    return {
        "decision_efficiency": decision_efficiency,
        "execution_friction": execution_friction,
        "stability_index": stability_index,
        "activity_profile": _activity_profile(
            decision_efficiency=decision_efficiency,
            execution_friction=execution_friction,
            stability_index=stability_index,
            signals_generated=signals_generated,
            total_windows=total_windows,
        ),
    }


def _activity_profile(
    *,
    decision_efficiency: float,
    execution_friction: float,
    stability_index: float,
    signals_generated: int,
    total_windows: int,
) -> str:
    if signals_generated == 0:
        return "inactive"
    if signals_generated <= total_windows and stability_index >= 0.9:
        return "low_signal_high_stability"
    if decision_efficiency < 0.5 or execution_friction >= 0.5:
        return "high_noise"
    if stability_index >= 0.9:
        return "stable_regime"
    return "active_regime"


def _stability_index(
    *,
    empty_windows: int,
    processing_failures: int,
    total_windows: int,
) -> float:
    if total_windows == 0:
        return 0.0
    return max(0.0, 1.0 - ((empty_windows + processing_failures) / total_windows))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _int_metric(metrics: dict[str, object], key: str) -> int:
    value = metrics.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _dict_metric(metrics: dict[str, object], key: str) -> dict[str, object]:
    value = metrics.get(key, {})
    if isinstance(value, dict):
        return value
    return {}
