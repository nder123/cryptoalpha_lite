from tests.signal_intelligence.semantic_containment_v1.containment_assertions import (
    assert_no_derived_summary,
    assert_observation_only_output,
    contained_observations,
    forbidden_narrative_terms,
)
from tests.signal_intelligence.semantic_containment_v1.fixtures import (
    AMBIGUOUS_CONTEXT_SET,
)


def test_signals_do_not_become_market_interpretation():
    output = contained_observations(AMBIGUOUS_CONTEXT_SET)

    assert_observation_only_output(output)
    assert_no_derived_summary(output, AMBIGUOUS_CONTEXT_SET)


def test_causal_and_market_view_language_is_rejected():
    forbidden_outputs = (
        "volatility increased because liquidity shifted",
        "observations create a market view",
        "signals indicate a trend interpretation",
        "this means execution conditions changed",
    )

    for output in forbidden_outputs:
        assert forbidden_narrative_terms(output)
