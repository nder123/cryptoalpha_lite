from __future__ import annotations

from typing import Mapping

SIMULATION_STATUSES = ("accepted", "rejected", "delayed")


def simulate_execution(decision: Mapping[str, object]) -> dict[str, object]:
    requested_status = str(decision.get("simulation_status", "accepted"))
    status = requested_status if requested_status in SIMULATION_STATUSES else "rejected"

    return {
        "decision_id": decision["decision_id"],
        "status": status,
    }
