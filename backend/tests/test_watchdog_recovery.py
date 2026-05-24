"""Tests for recovery action selection and budget enforcement."""
from __future__ import annotations

import pytest

from runtime.watchdog.recovery import (
    DEFAULT_BUDGET,
    FORBIDDEN_AUTORESTART,
    RestartLedger,
    select_action,
)
from runtime.watchdog.states import H


def test_forbidden_autorestart_set_contains_backend_and_watchdog():
    assert "cryptoalpha-backend.service" in FORBIDDEN_AUTORESTART
    assert "cryptoalpha-watchdog.service" in FORBIDDEN_AUTORESTART


def test_record_on_forbidden_raises():
    led = RestartLedger()
    with pytest.raises(PermissionError):
        led.record("cryptoalpha-backend.service", 0.0)


def test_would_exhaust_true_for_forbidden_unit():
    led = RestartLedger()
    assert led.would_exhaust("cryptoalpha-backend.service", 0.0)


def test_snapshots_budget_three_per_thirty_minutes():
    led = RestartLedger()
    now = 1000.0
    for i in range(3):
        assert not led.would_exhaust("cryptoalpha-snapshots.service", now + i)
        led.record("cryptoalpha-snapshots.service", now + i)
    # 4th attempt within window must be refused
    assert led.would_exhaust("cryptoalpha-snapshots.service", now + 60)


def test_budget_window_slides():
    led = RestartLedger()
    now = 1000.0
    for i in range(3):
        led.record("cryptoalpha-snapshots.service", now + i)
    # After 30 min + 1s, all prior records are pruned
    later = now + 30 * 60 + 2
    assert not led.would_exhaust("cryptoalpha-snapshots.service", later)


def test_default_budget_for_unknown_unit_is_two_per_fifteen_min():
    assert DEFAULT_BUDGET.max_count == 2
    assert DEFAULT_BUDGET.window_sec == 15 * 60


# ── select_action behavior per recovery table §3 ────────────────────────


def test_healthy_state_returns_no_action():
    a = select_action(state=H.HEALTHY, probes={}, ledger=RestartLedger(), now_ts=0.0)
    assert a.kind == "none"


def test_critical_returns_enter_safe_mode():
    a = select_action(state=H.CRITICAL, probes={}, ledger=RestartLedger(), now_ts=0.0)
    assert a.kind == "enter_safe_mode"


def test_safe_mode_state_does_nothing_more():
    a = select_action(state=H.SAFE_MODE, probes={}, ledger=RestartLedger(), now_ts=0.0)
    assert a.kind == "none"


def test_recovering_state_observes_only():
    a = select_action(state=H.RECOVERING, probes={}, ledger=RestartLedger(), now_ts=0.0)
    assert a.kind == "none"


def test_degraded_with_p5_fail_restarts_snapshots():
    a = select_action(
        state=H.DEGRADED,
        probes={"P5": "fail"},
        ledger=RestartLedger(),
        now_ts=0.0,
    )
    assert a.kind == "restart_unit"
    assert a.target == "cryptoalpha-snapshots.service"


def test_degraded_with_p4_fail_restarts_recommender():
    a = select_action(
        state=H.DEGRADED,
        probes={"P4": "fail"},
        ledger=RestartLedger(),
        now_ts=0.0,
    )
    assert a.kind == "restart_unit"
    assert a.target == "cryptoalpha-recommender.service"


def test_degraded_with_exhausted_budget_observes():
    led = RestartLedger()
    for i in range(3):
        led.record("cryptoalpha-snapshots.service", float(i))
    a = select_action(
        state=H.DEGRADED,
        probes={"P5": "fail"},
        ledger=led,
        now_ts=10.0,
    )
    assert a.kind == "observe"


def test_stalled_with_p3_fail_restarts_snapshots():
    a = select_action(
        state=H.STALLED,
        probes={"P3": "fail"},
        ledger=RestartLedger(),
        now_ts=0.0,
    )
    assert a.kind == "restart_unit"
    assert a.target == "cryptoalpha-snapshots.service"
