"""Shadow Runtime Bridge — non-invasive event observer.

Accepts execution events and records them in a structured trace log
without performing any real trading, risk modification, or side-effects.
No dependency on watchdog, chaos, or freeze_guard modules.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence


@dataclass(frozen=True)
class ShadowTraceEntry:
    """Single trace record captured by the shadow runtime."""

    event_type: str
    event_id: str
    timestamp: float
    payload: Dict[str, Any]


class ShadowRuntime:
    """Passively observes execution events without side-effects.

    Usage::

        shadow = ShadowRuntime()
        shadow.ingest(event_type="execution_report", event_id="d-1", payload={...})
        print(shadow.trace)  # list of ShadowTraceEntry
    """

    def __init__(self) -> None:
        self._trace: List[ShadowTraceEntry] = []

    def ingest(
        self,
        *,
        event_type: str,
        event_id: str,
        payload: Dict[str, Any] | None = None,
    ) -> ShadowTraceEntry:
        """Accept an event and append it to the trace log.

        Returns the created trace entry.  Never triggers order execution,
        risk changes, or any external I/O.
        """
        entry = ShadowTraceEntry(
            event_type=event_type,
            event_id=event_id,
            timestamp=time.monotonic(),
            payload=payload or {},
        )
        self._trace.append(entry)
        return entry

    @property
    def trace(self) -> Sequence[ShadowTraceEntry]:
        """Read-only view of all recorded trace entries."""
        return list(self._trace)

    def find(self, *, event_id: str) -> ShadowTraceEntry | None:
        """Lookup a single trace entry by event_id."""
        for entry in self._trace:
            if entry.event_id == event_id:
                return entry
        return None

    def clear(self) -> None:
        """Reset the trace log."""
        self._trace.clear()
