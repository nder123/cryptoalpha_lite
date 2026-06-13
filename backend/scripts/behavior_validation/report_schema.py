from __future__ import annotations


def build_report(
    *,
    run_id: str,
    signals: int,
    decisions: int,
    executions: int,
    metrics: dict[str, int],
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "signals": signals,
        "decisions": decisions,
        "executions": executions,
        "metrics": metrics,
    }
