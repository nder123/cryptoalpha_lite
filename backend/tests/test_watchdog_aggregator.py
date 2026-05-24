"""Tests for the aggregator: tier predicates, hysteresis, mode awareness."""
from __future__ import annotations

from runtime.watchdog.aggregator import (
    HysteresisCounters,
    Overrides,
    Tunables,
    evaluate,
)
from runtime.watchdog.states import H


def _probes(**overrides):
    base = {p: "pass" for p in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10")}
    base.update(overrides)
    return base


def _eval(prior, probes, counters=None, overrides=None, mode="OFFLINE", now=0.0, recovery=False):
    return evaluate(
        probes=probes,
        prior_state=prior,
        counters=counters or HysteresisCounters(),
        overrides=overrides or Overrides(),
        runtime_mode=mode,
        now_ts=now,
        tunables=Tunables(),
        recovery_action_emitted_recently=recovery,
    )


# ── Tier 1: overrides ───────────────────────────────────────────────────

def test_tier1_bootstrap_override_wins_over_everything():
    d = _eval(H.HEALTHY, _probes(P10="fail"), overrides=Overrides(bootstrap_in_progress=True))
    assert d.target_state == H.BOOTSTRAPPING
    assert d.tier == 1


def test_tier1_operator_safe_mode_in_paper_mode():
    d = _eval(
        H.HEALTHY,
        _probes(),
        overrides=Overrides(trading_enabled=False, safe_mode_reason="op_cmd"),
        mode="PAPER",
    )
    assert d.target_state == H.SAFE_MODE
    assert d.tier == 1


def test_tier1_safe_mode_does_not_trigger_in_offline_when_trading_disabled():
    """OFFLINE has trading meaningfully disabled by definition; SAFE_MODE is for LIVE/PAPER."""
    d = _eval(
        H.HEALTHY,
        _probes(),
        overrides=Overrides(trading_enabled=False),
        mode="OFFLINE",
    )
    assert d.target_state != H.SAFE_MODE


# ── Tier 2: P10 immediate CRITICAL ──────────────────────────────────────

def test_tier2_coherence_break_immediate_critical_no_hysteresis():
    c = HysteresisCounters()
    d = _eval(H.HEALTHY, _probes(P10="fail"), counters=c)
    assert d.target_state == H.CRITICAL
    assert d.tier == 2


def test_tier2_p10_unknown_treated_as_fail():
    d = _eval(H.HEALTHY, _probes(P10="unknown"))
    assert d.target_state == H.CRITICAL


# ── Tier 3: critical infra with hysteresis K_critical=3 ─────────────────

def test_tier3_critical_infra_requires_three_consecutive_fails():
    c = HysteresisCounters()
    # 1st fail
    d = _eval(H.HEALTHY, _probes(P2="fail"), counters=c)
    assert d.target_state == H.HEALTHY
    # 2nd fail
    d = _eval(H.HEALTHY, _probes(P2="fail"), counters=c)
    assert d.target_state == H.HEALTHY
    # 3rd fail → CRITICAL
    d = _eval(H.HEALTHY, _probes(P2="fail"), counters=c)
    assert d.target_state == H.CRITICAL
    assert d.tier == 3


def test_tier3_counter_resets_on_recovery():
    c = HysteresisCounters()
    _eval(H.HEALTHY, _probes(P2="fail"), counters=c)
    _eval(H.HEALTHY, _probes(P2="fail"), counters=c)
    # Recovery
    d = _eval(H.HEALTHY, _probes(), counters=c)
    assert d.target_state == H.HEALTHY
    assert c.critical_infra_consecutive == 0


# ── Tier 4: reconciliation impossible (LIVE/PAPER) ──────────────────────

def test_tier4_offline_mode_skips_reconciliation_check():
    """OFFLINE forces P8=pass per §3.2."""
    c = HysteresisCounters()
    for _ in range(10):
        d = _eval(H.HEALTHY, _probes(P8="fail"), counters=c, mode="OFFLINE")
    assert d.target_state == H.HEALTHY


def test_tier4_live_mode_stalls_after_k_stall_consecutive_p8_fails():
    c = HysteresisCounters()
    last = None
    for _ in range(5):  # K_stall = 5
        last = _eval(H.HEALTHY, _probes(P8="fail"), counters=c, mode="LIVE")
    assert last.target_state == H.STALLED


def test_tier4_stall_escalates_to_critical_after_t_stall():
    c = HysteresisCounters()
    # Reach STALLED at t=0
    for _ in range(5):
        _eval(H.HEALTHY, _probes(P8="fail"), counters=c, mode="LIVE", now=0.0)
    # Cross escalation timer (default 600s)
    d = _eval(H.STALLED, _probes(P8="fail"), counters=c, mode="LIVE", now=601.0)
    assert d.target_state == H.CRITICAL
    assert d.tier == 4


# ── Tier 7: DEGRADED hysteresis K_soft=3 ────────────────────────────────

def test_tier7_degraded_requires_three_consecutive_soft_fails():
    c = HysteresisCounters()
    for i in range(2):
        d = _eval(H.HEALTHY, _probes(P5="fail"), counters=c)
        assert d.target_state == H.HEALTHY, f"early degrade at i={i}"
    d = _eval(H.HEALTHY, _probes(P5="fail"), counters=c)
    assert d.target_state == H.DEGRADED
    assert d.tier == 7


def test_tier7_degraded_then_recovery_requires_k_recover_green():
    c = HysteresisCounters()
    # Enter DEGRADED
    for _ in range(3):
        _eval(H.HEALTHY, _probes(P5="fail"), counters=c)
    # Single green pass → still DEGRADED (hold)
    d = _eval(H.DEGRADED, _probes(), counters=c)
    assert d.target_state == H.DEGRADED
    # Need K_recover=5 consecutive HEALTHY
    for _ in range(3):
        d = _eval(H.DEGRADED, _probes(), counters=c)
        assert d.target_state == H.DEGRADED
    d = _eval(H.DEGRADED, _probes(), counters=c)
    assert d.target_state == H.HEALTHY


# ── Tier 8: HEALTHY baseline ────────────────────────────────────────────

def test_tier8_all_green_yields_healthy():
    d = _eval(H.HEALTHY, _probes())
    assert d.target_state == H.HEALTHY
    assert d.tier == 8


def test_flapping_suppressed_within_k_soft_window():
    """One blip in P5 does not move HEALTHY → DEGRADED."""
    c = HysteresisCounters()
    _eval(H.HEALTHY, _probes(P5="fail"), counters=c)
    d = _eval(H.HEALTHY, _probes(), counters=c)
    assert d.target_state == H.HEALTHY
    assert c.soft_fail_consecutive == 0
