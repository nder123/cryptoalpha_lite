from tests.gate_f.execution_admission_v1.fixtures import (
    ADMISSION_REQUIRED_CASES,
    EXECUTION_ENGINE_REJECTED_INPUTS,
)

REJECTED_INPUT_TYPES = (
    "raw_signal",
    "unverified_decision",
    "implicit_instruction",
)


def test_execution_engine_rejects_raw_unverified_or_implicit_inputs():
    for rejected_input in EXECUTION_ENGINE_REJECTED_INPUTS:
        assert rejected_input["input_type"] in REJECTED_INPUT_TYPES
        assert rejected_input["admission_token"] is None


def test_execution_path_requires_verified_decision_and_explicit_admission():
    executable_cases = [
        case for case in ADMISSION_REQUIRED_CASES if case["execution_permitted"]
    ]

    assert len(executable_cases) == 1
    executable_case = executable_cases[0]
    assert executable_case["decision_verified"] is True
    assert executable_case["admission_token"] == "explicit-gate-f-admission"
    assert executable_case["gate_f_approved"] is True
