from tests.gate_g.execution_runtime_admission_v1.fixtures import VALID_ADMISSION_OBJECTS

REQUIRED_ADMISSION_KEYS = {
    "admission_id",
    "admission_token",
    "gate_g_approved",
    "validated_decision_ref",
    "signal_context",
    "policy_context",
    "execution_permitted",
}


def test_admission_contract_contains_required_fields():
    for admission in VALID_ADMISSION_OBJECTS:
        assert set(admission) == REQUIRED_ADMISSION_KEYS
        assert admission["gate_g_approved"] is True
        assert admission["validated_decision_ref"].startswith("decision-")


def test_admission_contract_is_isolated_from_signal_and_policy_context():
    for admission in VALID_ADMISSION_OBJECTS:
        assert admission["signal_context"] is None
        assert admission["policy_context"] is None
        assert "signal" not in admission["validated_decision_ref"]
        assert "policy" not in admission["validated_decision_ref"]
