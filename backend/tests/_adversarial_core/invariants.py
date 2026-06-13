from collections.abc import Iterable, Mapping, Sequence

PROBABILITY_LANGUAGE = (
    "probability",
    "probable",
    "likely",
    "likelihood",
    "odds",
    "chance",
    "confidence",
)

DECISION_LANGUAGE = (
    "allow",
    "allowed",
    "deny",
    "denied",
    "denial",
    "decision",
    "readiness",
)

POLICY_LANGUAGE = (
    "policy",
    "approval granted",
    "approved",
    "rejection triggered",
    "gate should",
    "permits",
    "should be done",
    "what should",
)

STRATEGY_LANGUAGE = (
    "buy",
    "sell",
    "hold",
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

EXECUTION_INTENT_LANGUAGE = (
    "execute",
    "open position",
    "submit order",
    "route trade",
    "increase position",
    "reduce position",
    "auto execution",
    "implicit execution",
    "hidden execution",
    "direct execution",
    "execution shortcut",
    "execution trigger",
)

ACTION_LANGUAGE = (
    "action",
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
    "rating",
    "evaluation",
)

NARRATIVE_LANGUAGE = (
    "because",
    "bearish",
    "bullish",
    "caused",
    "due to",
    "environment",
    "implies",
    "indicate",
    "indicates",
    "interpretation",
    "market narrative",
    "market view",
    "means",
    "narrative",
    "outlook",
    "regime",
    "scenario",
    "state",
    "story",
    "therefore",
    "trend interpretation",
    "view",
)

INTERPRETIVE_LANGUAGE = (
    "suggest",
    "suggests",
    "imply",
    "aligns with",
    "hint",
    "hints",
)

STATE_RECONSTRUCTION_LANGUAGE = (
    "infers",
    "inferred",
    "reconstruct",
    "reconstructed",
    "restores decision logic",
    "decision logic",
    "hidden state",
    "inferred state",
    "implicit evaluation",
    "performance interpretation",
    "interpretation layer",
)

SIGNAL_FORBIDDEN_TERMS = (
    *PROBABILITY_LANGUAGE,
    *DECISION_LANGUAGE,
    *POLICY_LANGUAGE,
    *STRATEGY_LANGUAGE,
    *ACTION_LANGUAGE,
    *FUTURE_EXPECTATION,
    *CONTRACT_OR_VALIDATION_AUTHORITY,
    *SCORING_OR_RANKING,
    *INTERPRETIVE_LANGUAGE,
)

OBSERVATION_FORBIDDEN_TERMS = (
    *SIGNAL_FORBIDDEN_TERMS,
    *NARRATIVE_LANGUAGE,
)

BOUNDARY_FORBIDDEN_TERMS = (
    *NARRATIVE_LANGUAGE,
    *STATE_RECONSTRUCTION_LANGUAGE,
    *SCORING_OR_RANKING,
    *POLICY_LANGUAGE,
    *STRATEGY_LANGUAGE,
)


def assert_no_forbidden_semantics(signals: Iterable[str]) -> None:
    _assert_no_terms(signals, SIGNAL_FORBIDDEN_TERMS)


def assert_no_decision(signals: Iterable[str]) -> None:
    _assert_no_terms(signals, (*DECISION_LANGUAGE, *ACTION_LANGUAGE))


def assert_no_narrative(signals: Iterable[str]) -> None:
    _assert_no_terms(signals, NARRATIVE_LANGUAGE)


def assert_no_policy_inference(signals: Iterable[str]) -> None:
    _assert_no_terms(signals, POLICY_LANGUAGE)


def assert_no_execution_intent(signals: Iterable[str]) -> None:
    _assert_no_terms(signals, EXECUTION_INTENT_LANGUAGE)


def assert_no_state_reconstruction(signals: Iterable[str]) -> None:
    _assert_no_terms(signals, BOUNDARY_FORBIDDEN_TERMS)


def assert_order_invariant(
    baseline: Sequence[str],
    candidates: Iterable[Sequence[str]],
) -> None:
    baseline_signature = semantic_signature(baseline)

    for candidate in candidates:
        assert_no_forbidden_semantics(candidate)
        assert semantic_signature(candidate) == baseline_signature


def assert_frequency_invariant(
    one_occurrence: Sequence[str],
    repeated_occurrences: Sequence[str],
) -> None:
    assert_no_forbidden_semantics(one_occurrence)
    assert_no_forbidden_semantics(repeated_occurrences)
    assert semantic_signature(repeated_occurrences) == semantic_signature(
        one_occurrence
    )


def assert_observation_only_output(
    output: Sequence[str], source: Sequence[str]
) -> None:
    assert isinstance(output, tuple)
    assert output
    assert len(output) == len(source)
    assert semantic_signature(output) == semantic_signature(source)
    _assert_no_terms(output, OBSERVATION_FORBIDDEN_TERMS)


def assert_forbidden_terms_present(text: str, terms: Iterable[str]) -> None:
    found = forbidden_terms_in(text, terms)
    assert found, f"Expected forbidden terms in {text!r}"


def assert_explicit_admission_required(case: Mapping[str, object]) -> None:
    has_admission = bool(case["admission_token"]) and bool(case["gate_f_approved"])
    execution_allowed = bool(case["decision_verified"]) and has_admission

    assert case["execution_permitted"] is execution_allowed


def assert_execution_rejects_unadmitted_input(entry: Mapping[str, object]) -> None:
    assert entry["input_type"] in (
        "raw_signal",
        "unverified_decision",
        "implicit_instruction",
    )
    assert entry["admission_token"] is None


def semantic_signature(signals: Iterable[str]) -> frozenset[str]:
    return frozenset(_normalize(signal) for signal in signals)


def forbidden_terms_in(text: str, terms: Iterable[str]) -> tuple[str, ...]:
    normalized = _normalize(text)
    return tuple(term for term in terms if term in normalized)


def _assert_no_terms(signals: Iterable[str], terms: Iterable[str]) -> None:
    for signal in signals:
        forbidden_terms = forbidden_terms_in(signal, terms)
        assert forbidden_terms == (), (
            f"Value must remain invariant-safe: {signal!r}; "
            f"forbidden={forbidden_terms!r}"
        )


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("/", " ").replace("-", " ").split())
