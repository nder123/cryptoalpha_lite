import pytest

from tests._adversarial_core import attacks
from tests._adversarial_core.fixtures import (
    AMBIGUOUS_CONTEXT_SET,
    FORBIDDEN_NARRATIVE_OUTPUTS,
    OBSERVATION_CLUSTERS,
)
from tests._adversarial_core.invariants import (
    OBSERVATION_FORBIDDEN_TERMS,
    assert_forbidden_terms_present,
    assert_no_narrative,
    assert_observation_only_output,
    semantic_signature,
)


@pytest.mark.parametrize("signals", attacks.narrative_emergence_attack())
def test_semantic_narrative_inputs_remain_observation_only(signals: tuple[str, ...]):
    output = tuple(signals)

    assert_observation_only_output(output, signals)


def test_semantic_clusters_do_not_infer_state_or_story():
    for cluster_name, signals in OBSERVATION_CLUSTERS.items():
        output = tuple(signals)

        assert_observation_only_output(output, signals)
        assert cluster_name not in " ".join(output)


def test_semantic_composition_does_not_form_scenario_or_market_view():
    signals = (
        tuple(signal for cluster in OBSERVATION_CLUSTERS.values() for signal in cluster)
        + AMBIGUOUS_CONTEXT_SET[:8]
    )
    output = tuple(signals)

    assert 5 <= len(output) <= 20
    assert_observation_only_output(output, signals)
    assert semantic_signature(output) == semantic_signature(signals)


def test_semantic_forbidden_narratives_are_detected():
    for narrative in (
        FORBIDDEN_NARRATIVE_OUTPUTS + attacks.boundary_reconstruction_attack()
    ):
        assert_forbidden_terms_present(narrative, OBSERVATION_FORBIDDEN_TERMS)


def test_semantic_contextual_overreach_is_not_present_in_observations():
    assert_no_narrative(AMBIGUOUS_CONTEXT_SET)
