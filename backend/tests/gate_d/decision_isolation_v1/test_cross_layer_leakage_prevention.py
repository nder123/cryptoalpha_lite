from tests.gate_d.decision_isolation_v1.fixtures import (
    DECISION_TRAP_SIGNALS,
    FORBIDDEN_CROSS_LAYER_OUTPUTS,
    POLICY_AMBIGUOUS_SIGNAL_SETS,
)

CROSS_LAYER_DECISION_LANGUAGE = (
    "allowed",
    "denied",
    "validation policy",
    "overrides",
    "decision layer",
    "implicit policy",
    "map to",
    "trigger",
)


def test_signals_do_not_enter_decision_layer_through_implicit_mapping():
    signals = DECISION_TRAP_SIGNALS + tuple(
        signal for signal_set in POLICY_AMBIGUOUS_SIGNAL_SETS for signal in signal_set
    )
    output = tuple(signals)

    assert output == signals
    for observation in output:
        normalized = observation.lower()
        assert all(term not in normalized for term in CROSS_LAYER_DECISION_LANGUAGE)


def test_cross_layer_policy_leakage_outputs_are_forbidden():
    for output in FORBIDDEN_CROSS_LAYER_OUTPUTS:
        normalized = output.lower()
        assert any(term in normalized for term in CROSS_LAYER_DECISION_LANGUAGE)
