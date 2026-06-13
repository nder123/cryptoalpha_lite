from tests.signal_intelligence.semantic_containment_v1.containment_assertions import (
    assert_no_derived_summary,
    assert_observation_only_output,
    contained_observations,
    forbidden_narrative_terms,
)
from tests.signal_intelligence.semantic_containment_v1.fixtures import (
    AMBIGUOUS_CONTEXT_SET,
)


def test_correlated_observations_do_not_become_this_means_x():
    output = contained_observations(AMBIGUOUS_CONTEXT_SET)

    assert_observation_only_output(output)
    assert_no_derived_summary(output, AMBIGUOUS_CONTEXT_SET)


def test_contextual_overreach_phrasing_is_rejected():
    overreach_outputs = (
        "this means market risk is increasing",
        "correlated observations imply a hidden state",
        "signals therefore describe a future scenario",
        "the cluster indicates strategy readiness",
    )

    for output in overreach_outputs:
        assert forbidden_narrative_terms(output)
