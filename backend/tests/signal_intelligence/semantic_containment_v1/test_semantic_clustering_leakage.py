import pytest

from tests.signal_intelligence.semantic_containment_v1.containment_assertions import (
    assert_no_derived_summary,
    assert_observation_only_output,
    contained_observations,
    forbidden_narrative_terms,
)
from tests.signal_intelligence.semantic_containment_v1.fixtures import (
    OBSERVATION_CLUSTERS,
)


@pytest.mark.parametrize("cluster_name", tuple(OBSERVATION_CLUSTERS))
def test_related_signals_do_not_infer_hidden_state(cluster_name: str):
    signals = OBSERVATION_CLUSTERS[cluster_name]
    output = contained_observations(signals)

    assert_observation_only_output(output)
    assert_no_derived_summary(output, signals)
    assert cluster_name not in " ".join(output)


def test_cluster_labels_are_not_semantic_outputs():
    for cluster_name in OBSERVATION_CLUSTERS:
        assert forbidden_narrative_terms(cluster_name.replace("_", " ")) == ()
