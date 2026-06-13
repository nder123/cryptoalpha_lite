from tests.gate_e.system_boundary_isolation_v1.fixtures import (
    API_RESPONSE_EDGE_CASES,
    FORBIDDEN_API_RESPONSES,
)

API_INTERPRETATION_KEYS = (
    "explanation",
    "interpretation",
    "state",
    "scenario",
    "score",
    "evaluation",
    "narrative",
)

API_INTERPRETATION_LANGUAGE = (
    "narrative",
    "state",
    "strategy",
    "scenario",
    "score",
    "evaluation",
    "interpretation",
)


def test_api_response_contains_structured_signal_data_only():
    for response in API_RESPONSE_EDGE_CASES:
        assert set(response) == {"signal", "source", "timestamp_scope"}
        serialized = " ".join(response.values()).lower()
        assert all(term not in serialized for term in API_INTERPRETATION_LANGUAGE)


def test_api_interpretation_responses_are_forbidden():
    for response in FORBIDDEN_API_RESPONSES:
        assert any(key in response for key in API_INTERPRETATION_KEYS)
        serialized = " ".join(response.values()).lower()
        assert any(term in serialized for term in API_INTERPRETATION_LANGUAGE)
