import pytest

from tests.signal_intelligence.semantic_containment_v1.containment_assertions import (
    assert_no_derived_summary,
    assert_observation_only_output,
    contained_observations,
    forbidden_narrative_terms,
)
from tests.signal_intelligence.semantic_containment_v1.fixtures import (
    FORBIDDEN_NARRATIVE_OUTPUTS,
    NARRATIVE_TRAP_INPUTS,
)


@pytest.mark.parametrize("signals", NARRATIVE_TRAP_INPUTS)
def test_signal_sets_do_not_form_market_narrative(signals: tuple[str, ...]):
    output = contained_observations(signals)

    assert_observation_only_output(output)
    assert_no_derived_summary(output, signals)


@pytest.mark.parametrize("narrative", FORBIDDEN_NARRATIVE_OUTPUTS)
def test_explicit_narrative_outputs_are_forbidden(narrative: str):
    assert forbidden_narrative_terms(narrative)
