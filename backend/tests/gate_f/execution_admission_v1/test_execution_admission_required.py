from tests.gate_f.execution_admission_v1.fixtures import ADMISSION_REQUIRED_CASES


def test_execution_requires_explicit_admission_token_and_gate_f_approval():
    for case in ADMISSION_REQUIRED_CASES:
        has_admission = bool(case["admission_token"]) and case["gate_f_approved"]
        execution_allowed = case["decision_verified"] and has_admission

        assert case["execution_permitted"] is execution_allowed


def test_valid_decision_without_admission_cannot_execute():
    case = next(
        item
        for item in ADMISSION_REQUIRED_CASES
        if item["case_id"] == "valid-decision-without-admission"
    )

    assert case["decision_verified"] is True
    assert case["admission_token"] is None
    assert case["execution_permitted"] is False
