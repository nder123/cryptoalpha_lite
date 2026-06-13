from collections.abc import Callable, Sequence

from tests._adversarial_core import attacks
from tests._adversarial_core.fixtures import CLEAN_SIGNALS, MIXED_NOISE_SET
from tests._adversarial_core.invariants import (
    SIGNAL_FORBIDDEN_TERMS,
    assert_forbidden_terms_present,
    assert_frequency_invariant,
    assert_no_decision,
    assert_no_execution_intent,
    assert_no_forbidden_semantics,
    assert_no_narrative,
    assert_no_policy_inference,
    assert_no_state_reconstruction,
    assert_order_invariant,
    semantic_signature,
)

Invariant = Callable[[Sequence[str]], None]


def run(
    signals: Sequence[str],
    invariants: tuple[Invariant, ...] = (
        assert_no_forbidden_semantics,
        assert_no_decision,
        assert_no_narrative,
        assert_no_policy_inference,
        assert_no_execution_intent,
        assert_no_state_reconstruction,
    ),
) -> str:
    for invariant in invariants:
        invariant(signals)
    return "PASS"


def run_signal_attack_suite() -> str:
    run(CLEAN_SIGNALS)
    run(attacks.composition_attack())
    run(CLEAN_SIGNALS[:8] + MIXED_NOISE_SET)

    one_occurrence, repeated_occurrences = attacks.frequency_attack()
    assert_frequency_invariant(one_occurrence, repeated_occurrences)
    assert_order_invariant(CLEAN_SIGNALS, attacks.ordering_attack())

    for forbidden in attacks.paraphrase_attack():
        assert_forbidden_terms_present(forbidden, SIGNAL_FORBIDDEN_TERMS)

    assert semantic_signature(CLEAN_SIGNALS + CLEAN_SIGNALS) == semantic_signature(
        CLEAN_SIGNALS
    )
    return "PASS"
