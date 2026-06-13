from tests.gate_d.decision_isolation_v1.fixtures import (
    FORBIDDEN_POLICY_OUTPUTS,
    POLICY_AMBIGUOUS_SIGNAL_SETS,
)

ALLOWED_DENIED_LANGUAGE = (
    "allow",
    "allowed",
    "deny",
    "denied",
    "approval",
    "approved",
    "rejection",
    "reject",
    "gate",
    "block",
    "permits",
)


def test_signals_do_not_create_allowed_denied_semantics():
    for signals in POLICY_AMBIGUOUS_SIGNAL_SETS:
        output = tuple(signals)

        assert output == signals
        for observation in output:
            normalized = observation.lower()
            assert all(term not in normalized for term in ALLOWED_DENIED_LANGUAGE)


def test_policy_access_outputs_are_forbidden():
    for output in FORBIDDEN_POLICY_OUTPUTS:
        normalized = output.lower()
        assert any(term in normalized for term in ALLOWED_DENIED_LANGUAGE)
