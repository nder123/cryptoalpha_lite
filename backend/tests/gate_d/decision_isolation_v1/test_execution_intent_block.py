from tests.gate_d.decision_isolation_v1.fixtures import (
    EXECUTION_BIASED_INPUTS,
    FORBIDDEN_EXECUTION_INTENT_OUTPUTS,
)

EXECUTION_INTENT_LANGUAGE = (
    "prepare",
    "submit",
    "route",
    "order",
    "trade",
    "position",
    "execute",
    "strategy",
)


def test_execution_biased_inputs_do_not_emit_execution_intent():
    output = tuple(EXECUTION_BIASED_INPUTS)

    assert output == EXECUTION_BIASED_INPUTS
    for observation in output:
        normalized = observation.lower()
        assert all(term not in normalized for term in EXECUTION_INTENT_LANGUAGE)


def test_execution_intent_outputs_are_forbidden():
    for output in FORBIDDEN_EXECUTION_INTENT_OUTPUTS:
        normalized = output.lower()
        assert any(term in normalized for term in EXECUTION_INTENT_LANGUAGE)
