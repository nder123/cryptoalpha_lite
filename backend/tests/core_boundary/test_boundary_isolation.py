from tests._adversarial_core import attacks
from tests._adversarial_core.fixtures import API_RESPONSE_EDGE_CASES, RAW_SIGNAL_STREAMS
from tests._adversarial_core.invariants import (
    BOUNDARY_FORBIDDEN_TERMS as INVARIANT_BOUNDARY_FORBIDDEN_TERMS,
)
from tests._adversarial_core.invariants import (
    assert_forbidden_terms_present,
    assert_no_state_reconstruction,
)


def test_boundary_external_consumers_remain_semantically_blind():
    for signal_stream in RAW_SIGNAL_STREAMS:
        assert_no_state_reconstruction(signal_stream)


def test_boundary_logging_metrics_api_and_ui_reconstruction_attacks_are_detected():
    for output in attacks.boundary_reconstruction_attack():
        assert_forbidden_terms_present(output, INVARIANT_BOUNDARY_FORBIDDEN_TERMS)


def test_boundary_api_responses_remain_structured_signal_data_only():
    for response in API_RESPONSE_EDGE_CASES:
        assert set(response) == {"signal", "source", "timestamp_scope"}
        assert_no_state_reconstruction(tuple(response.values()))
