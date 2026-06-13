from collections.abc import Iterable, Sequence

FORBIDDEN_NARRATIVE_TERMS = (
    "action",
    "because",
    "bearish",
    "breakout",
    "bullish",
    "caused",
    "decision",
    "due to",
    "environment",
    "forecast",
    "implies",
    "indicate",
    "indicates",
    "interpretation",
    "market narrative",
    "market view",
    "means",
    "outlook",
    "regime",
    "scenario",
    "should",
    "state",
    "story",
    "strategy",
    "therefore",
    "trend",
    "view",
    "will",
)


def contained_observations(signals: Sequence[str]) -> tuple[str, ...]:
    return tuple(signals)


def observation_signature(signals: Iterable[str]) -> frozenset[str]:
    return frozenset(_normalize(signal) for signal in signals)


def assert_observation_only_output(output: Sequence[str]) -> None:
    assert isinstance(output, tuple)
    assert output
    for observation in output:
        forbidden = forbidden_narrative_terms(observation)
        assert forbidden == (), (
            f"Output must remain observation-only: {observation!r}; "
            f"forbidden={forbidden!r}"
        )


def assert_no_derived_summary(output: Sequence[str], source: Sequence[str]) -> None:
    assert len(output) == len(source)
    assert observation_signature(output) == observation_signature(source)


def forbidden_narrative_terms(text: str) -> tuple[str, ...]:
    normalized = _normalize(text)
    return tuple(term for term in FORBIDDEN_NARRATIVE_TERMS if term in normalized)


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").replace("/", " ").split())
