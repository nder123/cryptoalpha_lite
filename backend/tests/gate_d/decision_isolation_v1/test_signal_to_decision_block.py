from tests.gate_d.decision_isolation_v1.fixtures import (
    DECISION_TRAP_SIGNALS,
    FORBIDDEN_DECISION_OUTPUTS,
)

DECISION_LANGUAGE = (
    "execute",
    "open position",
    "buy",
    "sell",
    "hold",
    "action",
    "instruction",
    "trade",
)


def test_signals_remain_observations_not_decision_outputs():
    output = tuple(DECISION_TRAP_SIGNALS)

    assert output == DECISION_TRAP_SIGNALS
    for observation in output:
        normalized = observation.lower()
        assert all(term not in normalized for term in DECISION_LANGUAGE)


def test_explicit_signal_to_decision_outputs_are_blocked():
    for output in FORBIDDEN_DECISION_OUTPUTS:
        normalized = output.lower()
        assert any(term in normalized for term in DECISION_LANGUAGE)
