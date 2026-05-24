"""H states and the transition function δ.

Per docs/unified_health_state_machine_v1.md §1, §4.
"""
from __future__ import annotations

from enum import Enum


class H(str, Enum):
    BOOTSTRAPPING = "BOOTSTRAPPING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    STALLED = "STALLED"
    SAFE_MODE = "SAFE_MODE"
    CRITICAL = "CRITICAL"


# Allowed transitions per §4.1. Self-loops are allowed (idempotent).
# Anything not in this map for a (from_state) key is forbidden.
ALLOWED_TRANSITIONS: dict[H, frozenset[H]] = {
    H.BOOTSTRAPPING: frozenset({H.HEALTHY, H.CRITICAL, H.SAFE_MODE, H.BOOTSTRAPPING}),
    H.HEALTHY: frozenset({H.DEGRADED, H.STALLED, H.CRITICAL, H.SAFE_MODE, H.HEALTHY}),
    H.DEGRADED: frozenset(
        {H.HEALTHY, H.RECOVERING, H.STALLED, H.CRITICAL, H.SAFE_MODE, H.DEGRADED}
    ),
    H.STALLED: frozenset({H.DEGRADED, H.RECOVERING, H.CRITICAL, H.SAFE_MODE, H.STALLED}),
    H.RECOVERING: frozenset(
        {H.HEALTHY, H.DEGRADED, H.STALLED, H.CRITICAL, H.SAFE_MODE, H.RECOVERING}
    ),
    H.SAFE_MODE: frozenset({H.RECOVERING, H.CRITICAL, H.SAFE_MODE}),
    H.CRITICAL: frozenset({H.SAFE_MODE, H.RECOVERING, H.CRITICAL}),
}


# Forbidden transitions explicitly enumerated for documentation and assertions.
# Direct edges that must never occur per §4.2.
FORBIDDEN_DIRECT_TRANSITIONS: frozenset[tuple[H, H]] = frozenset(
    {
        (H.CRITICAL, H.HEALTHY),
        (H.SAFE_MODE, H.HEALTHY),
        (H.STALLED, H.HEALTHY),
        (H.BOOTSTRAPPING, H.DEGRADED),
        (H.BOOTSTRAPPING, H.STALLED),
        (H.BOOTSTRAPPING, H.RECOVERING),
    }
)


def is_allowed(prior: H, target: H) -> bool:
    """Return True iff `prior -> target` is a legal transition."""
    if (prior, target) in FORBIDDEN_DIRECT_TRANSITIONS:
        return False
    return target in ALLOWED_TRANSITIONS.get(prior, frozenset())


class IllegalTransition(Exception):
    """Raised when the watchdog attempts a forbidden transition."""


def assert_allowed(prior: H, target: H) -> None:
    if not is_allowed(prior, target):
        raise IllegalTransition(f"{prior.value} -> {target.value} is not allowed")
