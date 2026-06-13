from tests._adversarial_core.invariants import (
    EXECUTION_INTENT_LANGUAGE,
    assert_forbidden_terms_present,
)
from tests.gate_g.execution_runtime_admission_v1.fixtures import (
    INVALID_EXECUTION_ATTEMPTS,
    VALID_ADMISSION_OBJECTS,
)


def test_execution_is_gated_operation_only():
    for admission in VALID_ADMISSION_OBJECTS:
        assert admission["admission_token"] == "explicit-gate-g-admission"
        assert admission["gate_g_approved"] is True
        assert admission["validated_decision_ref"]
        assert admission["execution_permitted"] is True


def test_execution_cannot_occur_without_explicit_admission():
    for attempt in INVALID_EXECUTION_ATTEMPTS:
        assert attempt["admission_token"] is None
        assert attempt["gate_g_approved"] is False
        assert attempt["execution_permitted"] is False
        assert_forbidden_terms_present(attempt["payload"], EXECUTION_INTENT_LANGUAGE)
