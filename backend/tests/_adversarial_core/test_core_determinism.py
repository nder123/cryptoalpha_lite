from tests._adversarial_core import attacks
from tests._adversarial_core.assertion_engine import run, run_signal_attack_suite
from tests._adversarial_core.fixtures import CLEAN_SIGNALS
from tests._adversarial_core.invariants import semantic_signature


def test_attack_generators_are_repeatable():
    assert attacks.paraphrase_attack() == attacks.paraphrase_attack()
    assert attacks.composition_attack() == attacks.composition_attack()
    assert attacks.ordering_attack() == attacks.ordering_attack()
    assert attacks.frequency_attack() == attacks.frequency_attack()
    assert attacks.narrative_emergence_attack() == attacks.narrative_emergence_attack()
    assert attacks.decision_leakage_attack() == attacks.decision_leakage_attack()
    assert attacks.execution_bypass_attack() == attacks.execution_bypass_attack()
    assert (
        attacks.boundary_reconstruction_attack()
        == attacks.boundary_reconstruction_attack()
    )


def test_assertion_engine_is_repeatable_for_same_input():
    assert run(CLEAN_SIGNALS) == "PASS"
    assert run(CLEAN_SIGNALS) == "PASS"
    assert run_signal_attack_suite() == "PASS"
    assert run_signal_attack_suite() == "PASS"


def test_semantic_signature_is_input_deterministic():
    assert semantic_signature(CLEAN_SIGNALS) == semantic_signature(CLEAN_SIGNALS)
    assert semantic_signature(tuple(reversed(CLEAN_SIGNALS))) == semantic_signature(
        CLEAN_SIGNALS
    )
