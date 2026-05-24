"""S1-08 Chaos recovery drills.

Each test is a formal scenario that asserts a specific recovery invariant.
The harness mocks systemd/exchange/journald; the watchdog logic runs unchanged.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from runtime.chaos.harness import (
    DrillResult,
    all_pass,
    repeat,
    run_drill,
    with_fail,
)
from runtime.watchdog.states import (
    ALLOWED_TRANSITIONS,
    FORBIDDEN_DIRECT_TRANSITIONS,
    H,
    IllegalTransition,
    assert_allowed,
)


# ── D1: P10 coherence break → immediate CRITICAL (no hysteresis) ──────


def test_drill_d1_coherence_break_is_immediate_critical(tmp_path):
    # Single failing P10 must cross to CRITICAL on first non-bootstrap eval.
    seq = [all_pass(), with_fail("P10"), with_fail("P10")]
    res = run_drill(tmp_root=tmp_path, probe_sequence=seq, runtime_mode="OFFLINE")
    # We expect at least one CRITICAL transition triggered by P10.
    assert any(t["to"] == "CRITICAL" for t in res.transitions), res.transitions
    # The trigger predicate must be coherence_break
    crit = [t for t in res.transitions if t["to"] == "CRITICAL"][0]
    assert crit["trigger"]["predicate"] == "coherence_break"


# ── D2: persistent soft fail → DEGRADED → recovery restart ────────────


def test_drill_d2_degraded_triggers_restart_snapshots(tmp_path):
    # 5 evals with P5 failing → K_soft=3 trips DEGRADED at iteration 3,
    # recovery action selects snapshots restart.
    seq = repeat(with_fail("P5"), 8)
    res = run_drill(tmp_root=tmp_path, probe_sequence=seq, runtime_mode="OFFLINE")
    assert any(t["to"] == "DEGRADED" for t in res.transitions)
    assert "cryptoalpha-snapshots.service" in res.restart_attempts


# ── D3: restart budget exhaustion ───────────────────────────────────────


def test_drill_d3_budget_exhaustion_caps_restarts(tmp_path):
    # Even under continuous P5 fail, snapshots can be restarted at most 3
    # times per 30 min window. We drive ~20 iterations with 1s steps so the
    # ledger window never slides past. Expect ≤ 3 snapshots restarts.
    seq = repeat(with_fail("P5"), 30)
    res = run_drill(
        tmp_root=tmp_path,
        probe_sequence=seq,
        runtime_mode="OFFLINE",
        clock_step_sec=1.0,
    )
    n = res.restart_attempts.count("cryptoalpha-snapshots.service")
    assert n <= 3, f"snapshots restarted {n} times — budget breached"


# ── D4: STALLED → CRITICAL escalation after T_stall_to_critical ────────


def test_drill_d4_stall_escalates_to_critical(tmp_path):
    # LIVE mode + P8 fail → STALLED after K_stall=5 evals; then advance the
    # clock past T_stall_to_critical_sec (default 600) to force escalation.
    seq = repeat(with_fail("P8"), 20)
    res = run_drill(
        tmp_root=tmp_path,
        probe_sequence=seq,
        runtime_mode="LIVE",
        clock_step_sec=60.0,  # 20 ticks × 60s = 1200s → crosses 600s threshold
    )
    states = [t["to"] for t in res.transitions]
    assert "STALLED" in states or "CRITICAL" in states
    assert "CRITICAL" in states, f"escalation never reached CRITICAL: {states}"


# ── D5: operator SAFE_MODE entry is immediate ──────────────────────────


def test_drill_d5_operator_safe_mode_is_immediate(tmp_path):
    # PAPER mode + trading_enabled=false on iteration 2.
    seq = [all_pass(), all_pass(), all_pass()]
    overrides = [
        {},
        {"trading_enabled": False, "safe_mode_reason": "op_cmd"},
        {"trading_enabled": False, "safe_mode_reason": "op_cmd"},
    ]
    res = run_drill(
        tmp_root=tmp_path,
        probe_sequence=seq,
        overrides_sequence=overrides,
        runtime_mode="PAPER",
    )
    assert any(t["to"] == "SAFE_MODE" for t in res.transitions)


# ── D6: SAFE_MODE → HEALTHY direct is forbidden by δ ───────────────────


def test_drill_d6_forbidden_direct_safe_mode_to_healthy():
    """The transition function must reject SAFE_MODE → HEALTHY. This is the
    invariant the operator-only exit rule (I-S6) rests on."""
    assert (H.SAFE_MODE, H.HEALTHY) in FORBIDDEN_DIRECT_TRANSITIONS
    with pytest.raises(IllegalTransition):
        assert_allowed(H.SAFE_MODE, H.HEALTHY)


# ── D7: critical infra (backend down) triggers SAFE_MODE action ───────


def test_drill_d7_critical_infra_triggers_safe_mode_action(tmp_path):
    # P2 (API health) fail for K_critical=3 evals → CRITICAL → recovery
    # action = enter_safe_mode. SAFE_MODE entries list must be non-empty.
    seq = repeat(with_fail("P2"), 10)
    res = run_drill(tmp_root=tmp_path, probe_sequence=seq, runtime_mode="PAPER")
    assert any(t["to"] == "CRITICAL" for t in res.transitions)
    # CRITICAL → enter_safe_mode action emits a safe_mode entry.
    assert len(res.safe_mode_entries) >= 1


# ── D8: bounded recovery proof — restart count never grows unboundedly ─


def test_drill_d8_bounded_recovery_under_continuous_failure(tmp_path):
    # 100 iterations with P5 failing + P4 failing → both units may restart
    # but each is hard-capped at 3 per 30-min window. Plus, after CRITICAL is
    # reached, no further restarts (only enter_safe_mode).
    seq = repeat(with_fail("P4", "P5"), 100)
    res = run_drill(
        tmp_root=tmp_path,
        probe_sequence=seq,
        runtime_mode="OFFLINE",
        clock_step_sec=1.0,
    )
    snaps = res.restart_attempts.count("cryptoalpha-snapshots.service")
    rec = res.restart_attempts.count("cryptoalpha-recommender.service")
    assert snaps <= 3
    assert rec <= 3
    # Backend MUST NEVER be auto-restarted under any chaos.
    assert "cryptoalpha-backend.service" not in res.restart_attempts


# ── D9: backend service is FORBIDDEN_AUTORESTART under any scenario ───


def test_drill_d9_backend_never_autorestarted(tmp_path):
    # Even with P1 (backend) failing for many iterations, the watchdog must
    # not attempt to restart it. It must transition to CRITICAL and stop.
    seq = repeat(with_fail("P1"), 30)
    res = run_drill(tmp_root=tmp_path, probe_sequence=seq, runtime_mode="OFFLINE")
    assert "cryptoalpha-backend.service" not in res.restart_attempts
    assert any(t["to"] == "CRITICAL" for t in res.transitions)


# ── D10: artifact integrity — every drill produces valid jsonl + json ─


@pytest.mark.parametrize("seq", [
    [all_pass()] * 6,
    repeat(with_fail("P5"), 10),
    repeat(with_fail("P10"), 4),
    repeat(with_fail("P2"), 8),
])
def test_drill_d10_artifacts_always_valid(tmp_path, seq):
    res = run_drill(tmp_root=tmp_path, probe_sequence=seq, runtime_mode="OFFLINE")
    assert res.artifact_valid, f"artifact invalid; state={res.artifact_state}"
    # Every persisted transition must have non-empty from/to and valid trigger.
    for t in res.transitions:
        assert t.get("from") and t.get("to")
        assert "trigger" in t and t["trigger"].get("predicate")
        assert t.get("schema") == "runtime_health_transition.v1"


# ── D11: hysteresis suppression of a single blip ──────────────────────


def test_drill_d11_single_blip_does_not_degrade(tmp_path):
    # Sequence: pass, P5 fail, pass, pass, pass → counter reset; no DEGRADED.
    seq = [all_pass(), with_fail("P5")] + [all_pass()] * 6
    res = run_drill(tmp_root=tmp_path, probe_sequence=seq, runtime_mode="OFFLINE")
    states = [t["to"] for t in res.transitions]
    assert "DEGRADED" not in states


# ── D12: δ closure — no transition produced outside ALLOWED set ───────


def test_drill_d12_no_transition_violates_delta(tmp_path):
    """Adversarial sequence and a 'random walk' must never produce an
    illegal transition. δ closure across the entire run."""
    seq = (
        [all_pass()]
        + repeat(with_fail("P5"), 5)
        + repeat(with_fail("P10"), 2)
        + [all_pass()] * 3
        + repeat(with_fail("P2"), 4)
        + [all_pass()] * 5
    )
    res = run_drill(tmp_root=tmp_path, probe_sequence=seq, runtime_mode="OFFLINE")
    for t in res.transitions:
        frm = H(t["from"])
        to = H(t["to"])
        assert to in ALLOWED_TRANSITIONS.get(frm, frozenset()), (
            f"illegal transition produced: {frm.value} -> {to.value}"
        )
