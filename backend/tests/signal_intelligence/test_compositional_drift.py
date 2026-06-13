from tests.signal_intelligence.fixtures.signals_v1 import CLEAN_SIGNALS
from tests.signal_intelligence.semantic_guardrails_v1 import (
    assert_no_forbidden_semantics,
    semantic_signature,
)


def test_composed_signals_remain_independent_observations():
    composed_signals = CLEAN_SIGNALS[:25]

    assert_no_forbidden_semantics(composed_signals)
    assert semantic_signature(composed_signals) == frozenset(composed_signals)


def test_composition_does_not_form_market_view_or_implicit_scoring():
    composed_signals = CLEAN_SIGNALS[:25]
    composition_text = " ".join(composed_signals)

    assert_no_forbidden_semantics(composed_signals)
    assert "market view" not in composition_text
    assert "score" not in composition_text
    assert "rank" not in composition_text
    assert "weight" not in composition_text
    assert "strategy" not in composition_text
