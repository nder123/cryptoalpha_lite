from tests._adversarial_core.invariants import (
    EXECUTION_INTENT_LANGUAGE,
    assert_forbidden_terms_present,
)
from tests.gate_g.execution_runtime_admission_v1.fixtures import BYPASS_SIMULATION_CASES


def test_upstream_layers_cannot_bypass_execution_admission():
    for case in BYPASS_SIMULATION_CASES:
        assert case["source"] in {"signal", "policy", "decision"}
        assert case["admission_token"] is None
        assert case["execution_permitted"] is False


def test_bypass_attempts_are_explicitly_forbidden_cases():
    for case in BYPASS_SIMULATION_CASES:
        assert_forbidden_terms_present(
            case["bypass_attempt"],
            (*EXECUTION_INTENT_LANGUAGE, "execution bypass"),
        )
