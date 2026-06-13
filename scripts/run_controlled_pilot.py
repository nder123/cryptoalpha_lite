#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# isort: off
from app.services.contracts.event_contract import (  # noqa: E402
    check_lineage_compatibility,
    validate_batch,
)
from app.services.validation.contract_registry import ContractRegistry  # noqa: E402
from app.services.validation.core import ValidationCore  # noqa: E402
from app.services.validation.cross_module_consistency import (  # noqa: E402
    check_event_bus_coverage,
    check_event_contract,
    check_lineage_coverage,
    check_risk_coverage,
)
from app.services.validation.event_lineage import LineageEvent  # noqa: E402
from app.services.validation.event_lineage import validate_event_lineage  # noqa: E402

# isort: on


def main() -> int:
    try:
        result = _run_synthetic_pilot()
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "decision_trace": "",
                    "lineage_trace": "",
                    "contract_trace": "",
                    "final_decision": f"exception:{type(exc).__name__}",
                },
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "RUNNING" else 1


def _run_synthetic_pilot() -> dict[str, str]:
    decision_id = "decision-controlled-pilot"
    execution_id = "execution-controlled-pilot"
    decision_payload = {
        "trace_id": "trace-controlled-pilot-decision",
        "decision": "ALLOW",
    }
    raw_events = [
        _raw_event("pilot_input", "trace-controlled-pilot-input", None),
        _raw_event(
            "pilot_risk",
            "trace-controlled-pilot-risk",
            "trace-controlled-pilot-input",
        ),
        _raw_event(
            "pilot_decision",
            "trace-controlled-pilot-decision",
            "trace-controlled-pilot-risk",
        ),
    ]
    event_lineage = [
        LineageEvent(
            event_id="event-controlled-pilot-input",
            trace_id="trace-controlled-pilot",
        ),
        LineageEvent(
            event_id="event-controlled-pilot-risk",
            trace_id="trace-controlled-pilot",
            parent_id="event-controlled-pilot-input",
        ),
        LineageEvent(
            event_id="event-controlled-pilot-decision",
            trace_id="trace-controlled-pilot",
            parent_id="event-controlled-pilot-risk",
        ),
    ]

    event_contract_result = validate_batch(raw_events)
    contract_result = ContractRegistry().evaluate(decision_payload)
    trace_lineage_result = check_lineage_compatibility(raw_events)
    event_lineage_report = validate_event_lineage(event_lineage)
    consistency_results = {
        "event_contract": check_event_contract(raw_events).ok,
        "risk_coverage": check_risk_coverage([decision_id], {decision_id: {}}).ok,
        "event_bus_coverage": check_event_bus_coverage(
            [execution_id],
            {execution_id: {}},
        ).ok,
        "lineage_coverage": check_lineage_coverage(
            [decision_id],
            {decision_id: {"event_id": "event-controlled-pilot-decision"}},
        ).ok,
    }
    final_decision = ValidationCore().evaluate(decision_payload, context={})

    status = "RUNNING"
    if not contract_result.get("valid"):
        status = "HALTED"
    elif event_contract_result:
        status = "HALTED"
    elif trace_lineage_result or not event_lineage_report.passed:
        status = "HALTED"
    elif not all(consistency_results.values()):
        status = "HALTED"
    elif final_decision is None:
        status = "HALTED"

    return {
        "status": status,
        "decision_trace": _json_string(
            {
                "validation_core": {
                    "allowed": final_decision.allowed,
                    "reasons": final_decision.reasons,
                    "warnings": final_decision.warnings,
                },
                "consistency": consistency_results,
            }
        ),
        "lineage_trace": _json_string(
            {
                "trace_level": trace_lineage_result,
                "event_level_passed": event_lineage_report.passed,
                "event_level_violations": [
                    violation.code for violation in event_lineage_report.violations
                ],
            }
        ),
        "contract_trace": _json_string(contract_result),
        "final_decision": "ALLOW" if final_decision.allowed else "DENY",
    }


def _raw_event(event_type: str, trace_id: str, parent_id: str | None) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "trace_id": trace_id,
        "parent_id": parent_id,
        "timestamp": 1.0,
        "source_module": "controlled_pilot_wrapper",
    }


def _json_string(value: object) -> str:
    return json.dumps(value, sort_keys=True)


if __name__ == "__main__":
    sys.exit(main())
