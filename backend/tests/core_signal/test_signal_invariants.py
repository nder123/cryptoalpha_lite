from tests._adversarial_core import attacks
from tests._adversarial_core.assertion_engine import run, run_signal_attack_suite
from tests._adversarial_core.fixtures import (
    CLEAN_SIGNALS,
    LATENT_STRATEGY_PROBE_SIGNALS,
    MIXED_NOISE_SET,
)
from tests._adversarial_core.invariants import (
    SIGNAL_FORBIDDEN_TERMS,
    assert_forbidden_terms_present,
    assert_frequency_invariant,
    assert_no_forbidden_semantics,
    assert_order_invariant,
    semantic_signature,
)


def test_signal_invariant_suite_runs_through_shared_engine():
    assert run_signal_attack_suite() == "PASS"


def test_signal_paraphrase_attacks_are_rejected_by_shared_terms():
    for paraphrase in attacks.paraphrase_attack():
        assert_forbidden_terms_present(paraphrase, SIGNAL_FORBIDDEN_TERMS)


def test_signal_order_frequency_and_noise_are_invariant():
    one_occurrence, repeated_occurrences = attacks.frequency_attack()
    assert_frequency_invariant(one_occurrence, repeated_occurrences)
    assert_order_invariant(CLEAN_SIGNALS, attacks.ordering_attack())

    base_signals = CLEAN_SIGNALS[:8]
    noisy_signals = base_signals + MIXED_NOISE_SET
    assert_no_forbidden_semantics(noisy_signals)
    assert semantic_signature(base_signals).issubset(semantic_signature(noisy_signals))


def test_latent_strategy_probe_remains_signal_only():
    assert run(LATENT_STRATEGY_PROBE_SIGNALS) == "PASS"
