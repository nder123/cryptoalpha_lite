from __future__ import annotations

from collections.abc import Sequence


def build_metrics(
    signals: Sequence[object],
    decisions: Sequence[object],
    executions: Sequence[dict[str, object]],
) -> dict[str, int]:
    return {
        "signals_generated": len(signals),
        "decisions_generated": len(decisions),
        "executions_attempted": len(decisions),
        "executions_simulated": len(executions),
        "simulation_failures": sum(
            1 for execution in executions if execution["status"] == "rejected"
        ),
    }
