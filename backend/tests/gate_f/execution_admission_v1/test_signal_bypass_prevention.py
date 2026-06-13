from tests.gate_f.execution_admission_v1.fixtures import BYPASS_ATTEMPT_SCENARIOS

SIGNAL_BYPASS_LANGUAGE = (
    "direct execution",
    "bypass",
    "trigger",
    "execution",
)


def test_signals_cannot_bypass_decision_or_policy_layers():
    signal_attempts = (
        scenario
        for scenario in BYPASS_ATTEMPT_SCENARIOS
        if scenario["source"] == "signal"
    )

    for scenario in signal_attempts:
        assert scenario["source"] == "signal"
        assert "admission_token" not in scenario
        assert "execution_permitted" not in scenario


def test_signal_bypass_attempt_language_is_forbidden():
    forbidden = "signal direct execution trigger"

    assert any(term in forbidden for term in SIGNAL_BYPASS_LANGUAGE)
