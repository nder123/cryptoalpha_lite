from tests.signal_intelligence.semantic_containment_v1.containment_assertions import (
    assert_no_derived_summary,
    assert_observation_only_output,
    contained_observations,
    forbidden_narrative_terms,
    observation_signature,
)
from tests.signal_intelligence.semantic_containment_v1.fixtures import (
    AMBIGUOUS_CONTEXT_SET,
    OBSERVATION_CLUSTERS,
)


def test_composition_of_many_signals_remains_observation_list():
    signals = (
        tuple(signal for cluster in OBSERVATION_CLUSTERS.values() for signal in cluster)
        + AMBIGUOUS_CONTEXT_SET[:8]
    )
    output = contained_observations(signals)

    assert 5 <= len(output) <= 20
    assert_observation_only_output(output)
    assert_no_derived_summary(output, signals)


def test_cross_signal_composition_does_not_create_story_or_scenario():
    signals = tuple(
        signal for cluster in OBSERVATION_CLUSTERS.values() for signal in cluster
    )
    output = contained_observations(signals)
    combined = " ".join(output)

    assert observation_signature(output) == observation_signature(signals)
    assert "story" not in combined
    assert "scenario" not in combined
    assert "regime" not in combined
    assert forbidden_narrative_terms("signals form a scenario story")
