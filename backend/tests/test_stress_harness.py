from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
for p in (REPO_ROOT, BACKEND_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from stress import (
    STRESS_REGIMES,
    StressProfile,
    classify,
    generate_sequence,
    run_stress,
    stress_report,
)
from stress.classifier import (
    IDEMPOTENCY_BOUNDARY_LAYER,
    LEDGER_BRITTLE_REGION,
    PERMUTATION_SENSITIVE_ZONE,
    STABLE_CORE,
)


def _benign_profile(**kw) -> StressProfile:
    base = dict(
        n=32,
        seed=0,
        symbols=("BTC", "ETH"),
        known_symbols=("BTC", "ETH"),
        duplicate_id_rate=0.0,
        close_before_open=0.0,
        oversize_close=0.0,
        fee_interleave_rate=0.0,
        price_update_rate=0.0,
        invalid_size_rate=0.0,
        invalid_symbol_rate=0.0,
    )
    base.update(kw)
    return StressProfile(**base)


# --------------------------- generator ---------------------------- #


def test_generator_is_deterministic_under_seed() -> None:
    p = StressProfile(n=64, seed=42)
    a = generate_sequence(p)
    b = generate_sequence(p)
    assert a == b


def test_generator_respects_length() -> None:
    p = StressProfile(n=17, seed=1)
    seq = generate_sequence(p)
    assert len(seq) == 17


def test_generator_emits_only_known_action_types() -> None:
    seq = generate_sequence(StressProfile(n=128, seed=7))
    types = {e["type"] for e in seq}
    assert types <= {"open_position", "close_position", "charge_fee", "update_price"}


def test_different_seeds_produce_different_sequences() -> None:
    a = generate_sequence(StressProfile(n=64, seed=1))
    b = generate_sequence(StressProfile(n=64, seed=2))
    assert a != b


# ------------------------------ runner ---------------------------- #


def test_runner_pure_open_close_preserves_kernel_coherence() -> None:
    p = _benign_profile(n=40, seed=0)
    obs = run_stress(generate_sequence(p), known_symbols=("BTC", "ETH"))
    cls = classify(obs)
    # benign means no adversarial perturbations on input — kernel coherence
    # MUST hold, but permutation-frontier behavior is a property of the
    # ledger structure, not an instability finding.
    assert cls["metrics"]["invariant_break_count"] == 0
    assert cls["metrics"]["divergence_count"] == 0
    assert cls["metrics"]["replay_instability_score"] == 0
    assert LEDGER_BRITTLE_REGION not in cls["regimes"]


def test_runner_records_rejection_taxonomy_under_adversarial_profile() -> None:
    p = StressProfile(
        n=80,
        seed=11,
        symbols=("BTC", "ETH"),
        known_symbols=("BTC", "ETH"),
        duplicate_id_rate=0.0,
        close_before_open=0.5,
        oversize_close=0.3,
        fee_interleave_rate=0.0,
        price_update_rate=0.0,
        invalid_size_rate=0.2,
        invalid_symbol_rate=0.2,
    )
    obs = run_stress(generate_sequence(p), known_symbols=("BTC", "ETH"))
    assert obs["execution"]["rejected"] > 0
    reasons = obs["execution"]["reject_reasons"]
    # At least one of these must surface under such a profile.
    assert any(
        r in reasons
        for r in (
            "position_not_found",
            "insufficient_position_size",
            "invalid_size",
            "invalid_symbol",
        )
    )


def test_runner_kernel_coherence_invariants_hold_under_benign() -> None:
    obs = run_stress(generate_sequence(_benign_profile()), known_symbols=("BTC", "ETH"))
    inv = obs["lenses"]["portfolio_invariant"]
    # The only check allowed to fail under a benign profile is
    # `price_completeness` (no update_price was issued), which is
    # metadata-level, not a kernel invariant break.
    for c in inv["checks"]:
        if c["name"] == "price_completeness":
            continue
        assert c["ok"] is True, f"coherence check failed: {c['name']}"


def test_runner_cross_replay_metrics_present_and_well_typed() -> None:
    obs = run_stress(generate_sequence(_benign_profile()), known_symbols=("BTC", "ETH"))
    m = obs["lenses"]["cross_replay_metrics"]
    assert "feasibility_rate" in m
    assert 0.0 <= float(m["feasibility_rate"]) <= 1.0


# ---------------------------- classifier -------------------------- #


def test_classifier_idempotency_layer_when_duplicate_ids() -> None:
    p = StressProfile(
        n=60,
        seed=3,
        symbols=("BTC",),
        known_symbols=("BTC",),
        duplicate_id_rate=0.6,
        close_before_open=0.0,
        oversize_close=0.0,
        fee_interleave_rate=0.0,
        price_update_rate=0.0,
        invalid_size_rate=0.0,
        invalid_symbol_rate=0.0,
    )
    rpt = stress_report(p)
    # Either we triggered idempotent suppression OR rejections; both are valid
    # adversarial signatures. Assert that at least the regimes are non-empty
    # and that metrics are coherent.
    assert rpt["regimes"]
    assert set(rpt["regimes"]) <= set(STRESS_REGIMES)
    if rpt["execution"]["idempotent_suppressed"] > 0:
        assert IDEMPOTENCY_BOUNDARY_LAYER in rpt["regimes"]


def test_classifier_emits_only_declared_regimes() -> None:
    rpt = stress_report(StressProfile(n=80, seed=5))
    assert set(rpt["regimes"]) <= set(STRESS_REGIMES)


def test_classifier_stable_core_when_no_permutation_frontier() -> None:
    # A trivially monotone single-symbol sequence: open-then-close, no
    # adversarial rates, single permutation (the identity) — this is the
    # only configuration that should classify as pure stable_core.
    p = _benign_profile(n=2, seed=0, symbols=("BTC",), known_symbols=("BTC",))
    rpt = stress_report(p, cross_replay_permutations=1)
    assert STABLE_CORE in rpt["regimes"]
    assert LEDGER_BRITTLE_REGION not in rpt["regimes"]


# ------------------------------ report ---------------------------- #


def test_stress_report_is_deterministic_under_seed() -> None:
    a = stress_report(StressProfile(n=64, seed=99))
    b = stress_report(StressProfile(n=64, seed=99))
    # full report — including every lens output — must match byte-for-byte.
    assert a == b


def test_stress_report_metrics_shape() -> None:
    rpt = stress_report(StressProfile(n=32, seed=0))
    keys = {
        "invariant_break_count",
        "divergence_count",
        "permutation_sensitivity_rate",
        "order_sensitive",
        "replay_instability_score",
        "idempotent_suppressed",
        "rejected",
        "accepted",
    }
    assert keys <= set(rpt["metrics"].keys())


def test_stress_report_does_not_break_kernel_invariants_for_default_profile() -> None:
    rpt = stress_report(StressProfile(n=80, seed=12345))
    # Kernel invariants must hold regardless of adversarial input — that's the
    # whole point of the freeze. Brittle ledger ⇒ kernel bug, not a finding.
    assert LEDGER_BRITTLE_REGION not in rpt["regimes"]
    assert rpt["metrics"]["invariant_break_count"] == 0
    assert rpt["metrics"]["divergence_count"] == 0


def test_stress_report_high_rejection_profile_does_not_break_invariants() -> None:
    p = StressProfile(
        n=120,
        seed=7,
        symbols=("BTC", "ETH"),
        known_symbols=("BTC", "ETH"),
        duplicate_id_rate=0.4,
        close_before_open=0.4,
        oversize_close=0.3,
        fee_interleave_rate=0.2,
        price_update_rate=0.1,
        invalid_size_rate=0.1,
        invalid_symbol_rate=0.1,
    )
    from stress.classifier import CLOSURE_STRESS_FRONTIER

    rpt = stress_report(p)
    assert rpt["metrics"]["invariant_break_count"] == 0
    assert rpt["metrics"]["divergence_count"] == 0
    assert rpt["execution"]["rejected"] > 0
    # under such adversarial density, at least one permutation-related
    # regime must surface (frontier or sensitivity), or kernel must be
    # in stable_core. Coherence breakage is a kernel bug, not a finding.
    assert (
        PERMUTATION_SENSITIVE_ZONE in rpt["regimes"]
        or CLOSURE_STRESS_FRONTIER in rpt["regimes"]
        or rpt["regimes"] == [STABLE_CORE]
    )
