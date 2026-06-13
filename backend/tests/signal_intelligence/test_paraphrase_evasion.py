import pytest

from tests.signal_intelligence.fixtures.signals_v1 import (
    ADVERSARIAL_PARAPHRASES,
    CLEAN_SIGNALS,
)
from tests.signal_intelligence.semantic_guardrails_v1 import (
    assert_no_forbidden_semantics,
    forbidden_terms_in,
)


def test_clean_signals_remain_descriptive_under_paraphrase_guard():
    assert_no_forbidden_semantics(CLEAN_SIGNALS)


@pytest.mark.parametrize("signal", ADVERSARIAL_PARAPHRASES)
def test_paraphrased_forbidden_meaning_is_rejected(signal: str):
    forbidden_terms = forbidden_terms_in(signal)

    assert forbidden_terms
    assert any(
        term in forbidden_terms
        for term in (
            "probability",
            "suggests",
            "indicate",
            "indicates",
            "implies",
            "aligns with",
            "bias",
            "breakout",
            "continuation",
            "readiness",
            "favors",
            "supports",
            "entry",
            "strategy",
            "activation",
            "denial",
            "probable",
            "preference",
        )
    )
