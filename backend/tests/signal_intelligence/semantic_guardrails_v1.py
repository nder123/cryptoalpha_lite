from collections.abc import Iterable

PROBABILITY_LANGUAGE = (
    "probability",
    "probable",
    "likely",
    "likelihood",
    "odds",
    "chance",
    "confidence",
)

DECISION_FRAMING = (
    "allow",
    "allowed",
    "deny",
    "denied",
    "denial",
    "decision",
    "readiness",
)

STRATEGY_FRAMING = (
    "buy",
    "sell",
    "long",
    "short",
    "entry",
    "exit",
    "trade",
    "position",
    "strategy",
    "breakout",
    "continuation",
    "bias",
    "favors",
    "supports",
    "activation",
    "preference",
)

ACTION_FRAMING = (
    "action",
    "act",
    "execute",
    "execution should",
    "should",
    "must",
)

FUTURE_EXPECTATION = (
    "will",
    "forecast",
    "predict",
    "expected",
    "expectation",
    "future",
)

CONTRACT_OR_VALIDATION_AUTHORITY = (
    "contract",
    "contracts",
    "contract_rules",
    "validationcore",
    "validation_core",
    "lineage decision",
    "lineage verdict",
)

SCORING_OR_RANKING = (
    "score",
    "scoring",
    "rank",
    "ranking",
    "weight",
    "weighted",
    "significance",
    "priority",
)

INTERPRETIVE_LANGUAGE = (
    "suggest",
    "suggests",
    "indicate",
    "indicates",
    "imply",
    "implies",
    "aligns with",
    "hint",
    "hints",
)

FORBIDDEN_TERMS = (
    *PROBABILITY_LANGUAGE,
    *DECISION_FRAMING,
    *STRATEGY_FRAMING,
    *ACTION_FRAMING,
    *FUTURE_EXPECTATION,
    *CONTRACT_OR_VALIDATION_AUTHORITY,
    *SCORING_OR_RANKING,
    *INTERPRETIVE_LANGUAGE,
)


def semantic_signature(signals: Iterable[str]) -> frozenset[str]:
    assert_no_forbidden_semantics(signals)
    return frozenset(_normalize(signal) for signal in signals)


def assert_no_forbidden_semantics(signals: Iterable[str]) -> None:
    for signal in signals:
        forbidden_terms = forbidden_terms_in(signal)
        assert forbidden_terms == (), (
            f"Signal must remain descriptive-only: {signal!r}; "
            f"forbidden={forbidden_terms!r}"
        )


def forbidden_terms_in(signal: str) -> tuple[str, ...]:
    normalized = _normalize(signal)
    return tuple(term for term in FORBIDDEN_TERMS if term in normalized)


def _normalize(signal: str) -> str:
    return " ".join(signal.lower().replace("/", " ").replace("-", " ").split())
