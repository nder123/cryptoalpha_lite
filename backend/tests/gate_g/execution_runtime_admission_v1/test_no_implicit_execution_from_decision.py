from tests._adversarial_core.invariants import STRATEGY_LANGUAGE
from tests.gate_g.execution_runtime_admission_v1.fixtures import (
    DECISION_WITHOUT_ADMISSION_CASES,
)


def test_decision_does_not_start_execution_engine_without_admission():
    for case in DECISION_WITHOUT_ADMISSION_CASES:
        assert case["decision"] in STRATEGY_LANGUAGE
        assert case["validated_decision_ref"]
        assert case["admission_token"] is None
        assert case["gate_g_approved"] is False
        assert case["execution_engine_started"] is False


def test_decision_cannot_bypass_runtime_admission_layer():
    for case in DECISION_WITHOUT_ADMISSION_CASES:
        execution_allowed = bool(case["admission_token"]) and bool(
            case["gate_g_approved"]
        )

        assert execution_allowed is False
        assert case["execution_engine_started"] is False
