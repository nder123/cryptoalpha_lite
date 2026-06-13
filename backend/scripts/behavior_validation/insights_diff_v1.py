from __future__ import annotations

import json
from pathlib import Path


def diff_insights_files(
    previous_path: Path | str,
    current_path: Path | str,
) -> dict[str, object]:
    return diff_insights(
        _load_insights(Path(previous_path)),
        _load_insights(Path(current_path)),
    )


def diff_insights(
    previous: dict[str, object],
    current: dict[str, object],
) -> dict[str, object]:
    decision_efficiency_delta = _metric_delta(
        previous,
        current,
        "decision_efficiency",
    )
    execution_friction_delta = _metric_delta(
        previous,
        current,
        "execution_friction",
    )
    stability_index_delta = _metric_delta(
        previous,
        current,
        "stability_index",
    )

    return {
        "decision_efficiency_delta": decision_efficiency_delta,
        "execution_friction_delta": execution_friction_delta,
        "stability_index_delta": stability_index_delta,
        "regime_transition": {
            "from": str(previous.get("activity_profile", "unknown")),
            "to": str(current.get("activity_profile", "unknown")),
        },
        "drift_classification": _classify_drift(
            decision_efficiency_delta=decision_efficiency_delta,
            execution_friction_delta=execution_friction_delta,
            stability_index_delta=stability_index_delta,
        ),
    }


def _classify_drift(
    *,
    decision_efficiency_delta: float,
    execution_friction_delta: float,
    stability_index_delta: float,
) -> str:
    deltas = (
        decision_efficiency_delta,
        execution_friction_delta,
        stability_index_delta,
    )
    if any(abs(delta) > 0.25 for delta in deltas):
        return "CHAOTIC"

    degrading_count = sum(
        (
            decision_efficiency_delta < 0,
            execution_friction_delta > 0,
            stability_index_delta < 0,
        )
    )
    if degrading_count >= 2:
        return "DEGRADING"

    if (
        decision_efficiency_delta > 0
        and execution_friction_delta < 0
        and stability_index_delta > 0
    ):
        return "IMPROVING"

    return "STABLE"


def _metric_delta(
    previous: dict[str, object],
    current: dict[str, object],
    key: str,
) -> float:
    return _float_metric(current, key) - _float_metric(previous, key)


def _float_metric(insights: dict[str, object], key: str) -> float:
    value = insights.get(key, 0.0)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _load_insights(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}
