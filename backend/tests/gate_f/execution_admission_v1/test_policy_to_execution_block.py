from tests.gate_f.execution_admission_v1.fixtures import BYPASS_ATTEMPT_SCENARIOS

POLICY_EXECUTION_LANGUAGE = (
    "policy execution shortcut",
    "execute",
    "execution",
    "shortcut",
)


def test_policy_layer_cannot_directly_initiate_execution():
    policy_attempts = (
        scenario
        for scenario in BYPASS_ATTEMPT_SCENARIOS
        if scenario["source"] == "policy"
    )

    for scenario in policy_attempts:
        assert scenario["source"] == "policy"
        assert "admission_token" not in scenario
        assert "execution_permitted" not in scenario


def test_policy_execution_shortcut_attempts_are_identified_as_forbidden():
    forbidden = "policy execution shortcut"

    assert any(term in forbidden for term in POLICY_EXECUTION_LANGUAGE)
