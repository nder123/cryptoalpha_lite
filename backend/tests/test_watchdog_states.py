"""Tests for the transition function δ.

Per docs/unified_health_state_machine_v1.md §4 and watchdog_recovery_v1.md.
"""
from __future__ import annotations

import pytest

from runtime.watchdog.states import (
    ALLOWED_TRANSITIONS,
    FORBIDDEN_DIRECT_TRANSITIONS,
    H,
    IllegalTransition,
    assert_allowed,
    is_allowed,
)


def test_state_set_cardinality_is_seven():
    assert len(H) == 7


@pytest.mark.parametrize(
    "src,dst",
    [
        (H.CRITICAL, H.HEALTHY),
        (H.SAFE_MODE, H.HEALTHY),
        (H.STALLED, H.HEALTHY),
        (H.BOOTSTRAPPING, H.DEGRADED),
        (H.BOOTSTRAPPING, H.STALLED),
        (H.BOOTSTRAPPING, H.RECOVERING),
    ],
)
def test_forbidden_direct_transitions_are_rejected(src, dst):
    assert not is_allowed(src, dst)
    with pytest.raises(IllegalTransition):
        assert_allowed(src, dst)


@pytest.mark.parametrize(
    "src,dst",
    [
        (H.BOOTSTRAPPING, H.HEALTHY),
        (H.BOOTSTRAPPING, H.CRITICAL),
        (H.BOOTSTRAPPING, H.SAFE_MODE),
        (H.HEALTHY, H.DEGRADED),
        (H.HEALTHY, H.STALLED),
        (H.HEALTHY, H.CRITICAL),
        (H.HEALTHY, H.SAFE_MODE),
        (H.DEGRADED, H.HEALTHY),
        (H.DEGRADED, H.RECOVERING),
        (H.DEGRADED, H.STALLED),
        (H.DEGRADED, H.CRITICAL),
        (H.DEGRADED, H.SAFE_MODE),
        (H.STALLED, H.DEGRADED),
        (H.STALLED, H.RECOVERING),
        (H.STALLED, H.CRITICAL),
        (H.STALLED, H.SAFE_MODE),
        (H.RECOVERING, H.HEALTHY),
        (H.RECOVERING, H.DEGRADED),
        (H.RECOVERING, H.STALLED),
        (H.RECOVERING, H.CRITICAL),
        (H.RECOVERING, H.SAFE_MODE),
        (H.SAFE_MODE, H.RECOVERING),
        (H.SAFE_MODE, H.CRITICAL),
        (H.CRITICAL, H.SAFE_MODE),
        (H.CRITICAL, H.RECOVERING),
    ],
)
def test_allowed_transitions_are_reachable(src, dst):
    assert is_allowed(src, dst)


def test_self_loops_allowed_for_every_state():
    for s in H:
        assert is_allowed(s, s), f"self-loop missing for {s}"


def test_no_state_in_forbidden_is_also_in_allowed():
    """Forbidden directs must NOT appear in ALLOWED_TRANSITIONS."""
    for src, dst in FORBIDDEN_DIRECT_TRANSITIONS:
        assert dst not in ALLOWED_TRANSITIONS.get(src, frozenset()), (
            f"forbidden ({src}->{dst}) leaked into ALLOWED_TRANSITIONS"
        )


def test_safe_mode_exit_requires_recovering():
    """I-S6: SAFE_MODE cannot transition directly to HEALTHY."""
    assert not is_allowed(H.SAFE_MODE, H.HEALTHY)
    assert is_allowed(H.SAFE_MODE, H.RECOVERING)


def test_critical_can_only_reach_safemode_or_recovering():
    out = ALLOWED_TRANSITIONS[H.CRITICAL] - {H.CRITICAL}
    assert out == {H.SAFE_MODE, H.RECOVERING}
