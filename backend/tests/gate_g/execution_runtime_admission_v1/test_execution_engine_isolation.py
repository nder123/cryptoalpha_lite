from tests.gate_g.execution_runtime_admission_v1.fixtures import ENGINE_REJECTED_INPUTS

REJECTED_ENGINE_INPUT_TYPES = (
    "raw_signal",
    "unverified_decision",
    "policy_suggestion",
)


def test_execution_engine_rejects_upstream_layer_inputs():
    for rejected_input in ENGINE_REJECTED_INPUTS:
        assert rejected_input["input_type"] in REJECTED_ENGINE_INPUT_TYPES
        assert rejected_input["validated_decision_ref"] is None
        assert rejected_input["admission_token"] is None


def test_execution_input_must_be_validated_admission_object():
    for rejected_input in ENGINE_REJECTED_INPUTS:
        is_valid_admission_object = (
            rejected_input["validated_decision_ref"] is not None
            and rejected_input["admission_token"] is not None
        )

        assert is_valid_admission_object is False
