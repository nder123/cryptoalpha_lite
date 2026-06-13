from tests.gate_d.decision_isolation_v1.fixtures import DECISION_TRAP_SIGNALS

POLICY_OR_ACTION_LANGUAGE = (
    "should",
    "policy",
    "buy",
    "sell",
    "hold",
    "do",
    "execute",
    "action",
)


def test_strong_signal_combination_does_not_infer_what_should_be_done():
    output = tuple(DECISION_TRAP_SIGNALS)

    assert output == DECISION_TRAP_SIGNALS
    for observation in output:
        normalized = observation.lower()
        assert all(term not in normalized for term in POLICY_OR_ACTION_LANGUAGE)


def test_buy_sell_hold_policy_inference_is_forbidden():
    forbidden_outputs = (
        "buy should be selected",
        "sell should be selected",
        "hold should be selected",
        "policy should execute",
    )

    for output in forbidden_outputs:
        normalized = output.lower()
        assert any(term in normalized for term in POLICY_OR_ACTION_LANGUAGE)
