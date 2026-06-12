"""Runtime health artifact reader.

Reads a JSON health artifact written by the watchdog subsystem and exposes
a typed snapshot.  Falls back to UNKNOWN when the file is missing or corrupt,
and caches the last-good read so transient I/O failures degrade gracefully.

No async, no network, no heavy deps — just pathlib + json.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_logger = logging.getLogger(__name__)

_DEFAULT_ARTIFACT = (
    Path(__file__).resolve().parents[3] / "artifacts" / "runtime_health.json"
)

_default_reader: Optional["RuntimeHealthReader"] = None


@dataclass(frozen=True)
class RuntimeHealthSnapshot:
    """Parsed view of the runtime health artifact."""

    state: str
    stale: bool
    stale_reason: Optional[str]
    safe_mode_active: bool
    coherence_break_count: int
    since: Optional[str]
    reasons: List[str]


def _parse_snapshot(data: dict) -> RuntimeHealthSnapshot:
    state = str(data.get("state", "UNKNOWN")).upper()
    probes = data.get("probes") or {}
    coherence_breaks = sum(1 for v in probes.values() if v == "fail")
    return RuntimeHealthSnapshot(
        state=state,
        stale=False,
        stale_reason=None,
        safe_mode_active=state in {"SAFE_MODE", "CRITICAL"},
        coherence_break_count=coherence_breaks,
        since=data.get("since"),
        reasons=data.get("reasons") or [],
    )


def _unknown_snapshot(*, stale_reason: str) -> RuntimeHealthSnapshot:
    return RuntimeHealthSnapshot(
        state="UNKNOWN",
        stale=True,
        stale_reason=stale_reason,
        safe_mode_active=False,
        coherence_break_count=0,
        since=None,
        reasons=[],
    )


class RuntimeHealthReader:
    """Synchronous reader for the runtime health JSON artifact."""

    def __init__(self, *, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_ARTIFACT
        self._last_good: Optional[RuntimeHealthSnapshot] = None

    def read(self) -> RuntimeHealthSnapshot:
        if not self._path.exists():
            if self._last_good is not None:
                return RuntimeHealthSnapshot(
                    state=self._last_good.state,
                    stale=True,
                    stale_reason="file_missing",
                    safe_mode_active=self._last_good.safe_mode_active,
                    coherence_break_count=self._last_good.coherence_break_count,
                    since=self._last_good.since,
                    reasons=self._last_good.reasons,
                )
            return _unknown_snapshot(stale_reason="file_missing")

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            _logger.debug("runtime_health_parse_error", error=str(exc))
            if self._last_good is not None:
                return RuntimeHealthSnapshot(
                    state=self._last_good.state,
                    stale=True,
                    stale_reason="parse_error",
                    safe_mode_active=self._last_good.safe_mode_active,
                    coherence_break_count=self._last_good.coherence_break_count,
                    since=self._last_good.since,
                    reasons=self._last_good.reasons,
                )
            return _unknown_snapshot(stale_reason="parse_error")

        snap = _parse_snapshot(data)
        self._last_good = snap
        return snap


def get_default_reader() -> RuntimeHealthReader:
    """Return the process-wide default reader (lazy-initialized)."""
    global _default_reader  # noqa: PLW0603
    if _default_reader is None:
        _default_reader = RuntimeHealthReader()
    return _default_reader


def set_default_reader_for_tests(reader: RuntimeHealthReader | None) -> None:
    """Override the default reader for testing. Pass ``None`` to reset."""
    global _default_reader  # noqa: PLW0603
    _default_reader = reader
