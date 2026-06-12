"""Cross-module consistency checks (offline / no runtime dependencies).

Validates structural invariants between layers:
  A. risk_engine <-> trading_gate   – every trade decision has a risk result
  B. execution_engine <-> event_bus – every execution event is recorded
  C. trading_gate <-> event lineage – every decision appears in the lineage graph
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class ConsistencyResult:
    """Outcome of a single consistency check."""

    ok: bool
    missing: List[str] = field(default_factory=list)


# ── A. risk_engine <-> trading_gate ──────────────────────────────────────


def check_risk_coverage(
    decision_ids: Sequence[str],
    risk_results: Dict[str, object],
) -> ConsistencyResult:
    """Every trade decision must reference an existing risk result.

    Parameters
    ----------
    decision_ids:
        Identifiers of decisions emitted by *trading_gate* / CTO-AI.
    risk_results:
        Mapping ``{hypothesis_id: <risk assessment payload>}`` produced by
        *risk_engine*.  Only the key set is inspected.
    """
    missing = [did for did in decision_ids if did not in risk_results]
    return ConsistencyResult(ok=len(missing) == 0, missing=missing)


# ── B. execution_engine <-> event_bus ────────────────────────────────────


def check_event_bus_coverage(
    execution_ids: Sequence[str],
    event_bus_records: Dict[str, object],
) -> ConsistencyResult:
    """Every execution event must have a corresponding event_bus record.

    Parameters
    ----------
    execution_ids:
        Identifiers of execution reports produced by *execution_engine*.
    event_bus_records:
        Mapping ``{directive_id: <bus payload>}`` representing records
        persisted in the event bus.
    """
    missing = [eid for eid in execution_ids if eid not in event_bus_records]
    return ConsistencyResult(ok=len(missing) == 0, missing=missing)


# ── C. trading_gate <-> event lineage ────────────────────────────────────


def check_lineage_coverage(
    decision_ids: Sequence[str],
    lineage_graph: Dict[str, object],
) -> ConsistencyResult:
    """Every gate decision must be present in the lineage graph.

    Parameters
    ----------
    decision_ids:
        Identifiers of decisions that passed through *trading_gate*.
    lineage_graph:
        Mapping ``{decision_id: <lineage node>}`` representing the
        event-lineage graph.
    """
    missing = [did for did in decision_ids if did not in lineage_graph]
    return ConsistencyResult(ok=len(missing) == 0, missing=missing)
