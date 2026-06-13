from tests._adversarial_core import attacks
from tests._adversarial_core.fixtures import (
    ADMISSION_REQUIRED_CASES,
    BYPASS_ATTEMPT_SCENARIOS,
    EXECUTION_ENGINE_REJECTED_INPUTS,
    POLICY_AMBIGUOUS_SIGNAL_SETS,
    VALID_DECISIONS,
)
from tests._adversarial_core.invariants import (
    ACTION_LANGUAGE,
    DECISION_LANGUAGE,
    EXECUTION_INTENT_LANGUAGE,
    POLICY_LANGUAGE,
    STRATEGY_LANGUAGE,
    assert_execution_rejects_unadmitted_input,
    assert_explicit_admission_required,
    assert_forbidden_terms_present,
    assert_no_decision,
    assert_no_execution_intent,
    assert_no_policy_inference,
)


def test_transition_signals_do_not_become_decisions_or_policy():
    for signal_set in POLICY_AMBIGUOUS_SIGNAL_SETS:
        assert_no_decision(signal_set)
        assert_no_policy_inference(signal_set)


def test_transition_decision_and_policy_leakage_attacks_are_detected():
    for output in attacks.decision_leakage_attack():
        assert_forbidden_terms_present(
            output,
            (
                *DECISION_LANGUAGE,
                *POLICY_LANGUAGE,
                *EXECUTION_INTENT_LANGUAGE,
                *STRATEGY_LANGUAGE,
                *ACTION_LANGUAGE,
            ),
        )


def test_transition_decision_does_not_auto_execute():
    for decision in VALID_DECISIONS:
        assert decision["validation_allowed"] is True
        assert "admission_token" not in decision
        assert "execution_permitted" not in decision


def test_transition_execution_requires_explicit_gate_f_admission():
    for case in ADMISSION_REQUIRED_CASES:
        assert_explicit_admission_required(case)


def test_transition_signals_policy_and_decisions_cannot_bypass_execution():
    for scenario in BYPASS_ATTEMPT_SCENARIOS:
        assert "admission_token" not in scenario
        assert "execution_permitted" not in scenario
        assert_forbidden_terms_present(scenario["attempt"], EXECUTION_INTENT_LANGUAGE)


def test_transition_execution_engine_rejects_unadmitted_inputs():
    for rejected_input in EXECUTION_ENGINE_REJECTED_INPUTS:
        assert_execution_rejects_unadmitted_input(rejected_input)


def test_transition_execution_trigger_attacks_are_detected():
    for trigger in attacks.execution_bypass_attack():
        assert_forbidden_terms_present(
            trigger,
            (*EXECUTION_INTENT_LANGUAGE, *POLICY_LANGUAGE, *STRATEGY_LANGUAGE),
        )
    assert_no_execution_intent(("execution latency increased",))
