# Controlled Pilot Locked State

## Frozen modules

- `backend/app/services/validation/contracts.py`
- `backend/app/services/validation/contract_registry.py`
- `backend/app/services/validation/core.py`
- `backend/app/services/contracts/event_contract.py`
- `backend/app/services/validation/event_lineage.py`
- `backend/app/services/validation/cross_module_consistency.py`
- `docs/validation/gate_d_validation_surface.md`
- `docs/validation/gate_d_execution_trace_map.md`
- `docs/controlled_pilot/admission_gate_v1.md`
- `docs/controlled_pilot/execution_protocol_v1.md`
- `scripts/check_controlled_pilot_readiness.py`
- `scripts/run_controlled_pilot.py`

## Allowed modifications

- Documentation clarifications that do not change contract, validation, lineage,
  or execution semantics.
- Test-only additions that preserve existing expected outcomes and do not
  redefine pilot admission rules.
- Observability-only additions that do not alter final decision semantics.

## Re-evaluation rule

Any change to validation, contract, or lineage requires re-evaluation of
Controlled Pilot readiness.

No change may reinterpret `CONTRACT_RULES` outside `ContractRegistry`, redefine
final decision semantics outside `ValidationCore`, or collapse trace-level and
event-level lineage semantics without a new Controlled Pilot readiness review.
