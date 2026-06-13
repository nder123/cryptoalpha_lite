from tests.gate_f.execution_admission_v1.fixtures import (
    INVALID_EXECUTION_TRIGGERS,
    VALID_DECISIONS,
)

EXECUTION_TRIGGER_LANGUAGE = (
    "buy",
    "sell",
    "open position",
    "auto execution",
    "implicit execution",
    "hidden execution",
    "execute",
    "submit order",
)


def test_valid_decision_does_not_auto_become_execution():
    for decision in VALID_DECISIONS:
        assert decision["validation_allowed"] is True
        assert "admission_token" not in decision
        assert "execution_permitted" not in decision


def test_implicit_execution_triggers_are_forbidden():
    for trigger in INVALID_EXECUTION_TRIGGERS:
        normalized = trigger.lower()
        assert any(term in normalized for term in EXECUTION_TRIGGER_LANGUAGE)
