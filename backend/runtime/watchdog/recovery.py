"""Recovery action dispatch with bounded budgets.

Per docs/watchdog_recovery_v1.md §3, §4. Pure logic for budget bookkeeping;
the actual systemctl invocation is performed by the loop via a callable.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from .states import H


@dataclass(frozen=True)
class Budget:
    max_count: int
    window_sec: int


# Per-unit restart budgets per §4.
RESTART_BUDGETS: dict[str, Budget] = {
    "cryptoalpha-snapshots.service": Budget(max_count=3, window_sec=30 * 60),
    "cryptoalpha-recommender.service": Budget(max_count=3, window_sec=30 * 60),
}
DEFAULT_BUDGET = Budget(max_count=2, window_sec=15 * 60)

# Units the watchdog is FORBIDDEN from restarting automatically. Operator only.
FORBIDDEN_AUTORESTART: frozenset[str] = frozenset(
    {
        "cryptoalpha-backend.service",
        "cryptoalpha-watchdog.service",
    }
)


@dataclass
class RestartLedger:
    """Tracks restart timestamps per unit to enforce sliding-window budgets."""

    history: dict[str, deque[float]] = field(default_factory=dict)

    def _budget_for(self, unit: str) -> Budget:
        return RESTART_BUDGETS.get(unit, DEFAULT_BUDGET)

    def _prune(self, unit: str, now_ts: float) -> None:
        b = self._budget_for(unit)
        dq = self.history.setdefault(unit, deque())
        cutoff = now_ts - b.window_sec
        while dq and dq[0] < cutoff:
            dq.popleft()

    def would_exhaust(self, unit: str, now_ts: float) -> bool:
        """Check without recording: would this restart push us over budget?"""
        if unit in FORBIDDEN_AUTORESTART:
            return True
        self._prune(unit, now_ts)
        b = self._budget_for(unit)
        return len(self.history.get(unit, ())) >= b.max_count

    def record(self, unit: str, now_ts: float) -> None:
        """Record a restart attempt. Caller MUST check would_exhaust first."""
        if unit in FORBIDDEN_AUTORESTART:
            raise PermissionError(f"{unit} is forbidden from auto-restart")
        self._prune(unit, now_ts)
        self.history.setdefault(unit, deque()).append(now_ts)

    def attempts_in_window(self, unit: str, now_ts: float) -> int:
        self._prune(unit, now_ts)
        return len(self.history.get(unit, ()))


# Recovery action mapping per §3.
@dataclass(frozen=True)
class RecoveryAction:
    kind: str  # "restart_unit" | "enter_safe_mode" | "observe" | "none"
    target: str | None = None  # unit name when kind == "restart_unit"
    reason: str = ""


def select_action(
    *,
    state: H,
    probes: dict[str, str],
    ledger: RestartLedger,
    now_ts: float,
) -> RecoveryAction:
    """Choose at most one recovery action per loop iteration. Pure-ish: uses ledger."""
    if state in {H.HEALTHY, H.BOOTSTRAPPING, H.RECOVERING, H.SAFE_MODE}:
        return RecoveryAction(kind="none", reason=f"state_{state.value}_no_action")

    if state == H.CRITICAL:
        return RecoveryAction(kind="enter_safe_mode", reason="critical_entry")

    if state == H.DEGRADED:
        # P4 = recommender, P5 = snapshots freshness
        if probes.get("P5") == "fail" and not ledger.would_exhaust(
            "cryptoalpha-snapshots.service", now_ts
        ):
            return RecoveryAction(
                kind="restart_unit",
                target="cryptoalpha-snapshots.service",
                reason="p5_snapshot_stale",
            )
        if probes.get("P4") == "fail" and not ledger.would_exhaust(
            "cryptoalpha-recommender.service", now_ts
        ):
            return RecoveryAction(
                kind="restart_unit",
                target="cryptoalpha-recommender.service",
                reason="p4_recommender_inactive",
            )
        return RecoveryAction(kind="observe", reason="degraded_budget_exhausted_or_no_action")

    if state == H.STALLED:
        for unit, probe in (
            ("cryptoalpha-snapshots.service", "P3"),
            ("cryptoalpha-recommender.service", "P4"),
        ):
            if probes.get(probe) == "fail" and not ledger.would_exhaust(unit, now_ts):
                return RecoveryAction(
                    kind="restart_unit",
                    target=unit,
                    reason=f"{probe.lower()}_stalled",
                )
        return RecoveryAction(kind="observe", reason="stalled_budget_exhausted")

    return RecoveryAction(kind="none", reason="default")
