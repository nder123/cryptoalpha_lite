# Gate D Execution Trace Map

## Pipeline

```text
event
  -> validation
  -> contract evaluation
  -> lineage checks
  -> cross-module consistency
  -> decision output
```

## End-to-end validation trace map

| Step | Input shape | Output shape | Failure modes | Responsible module |
| --- | --- | --- | --- | --- |
| Event envelope validation | `Sequence[Dict[str, Any]]` raw events with `event_type`, `trace_id`, `parent_id`, `timestamp`, `source_module` | `Dict[int, list[str]]` or `ConsistencyResult` | Missing required field, non-string `event_type`, non-string `trace_id`, non-numeric `timestamp`, non-string `source_module` | `app.services.contracts.event_contract.validate_batch`, `app.services.validation.cross_module_consistency.check_event_contract` |
| Contract evaluation | `Mapping[str, object]` decision payload with `trace_id` and `decision` | `dict[str, object]` with `valid` and `violations`; normalized to `ValidationResult` by Core | Missing trace, terminal `DENY`, terminal `REJECT` | `app.services.validation.contract_registry.ContractRegistry.evaluate`, orchestrated by `ValidationCore.evaluate` |
| Trace-level lineage check | `Sequence[Dict[str, Any]]` raw events | `list[str]` violations | Non-null `parent_id` does not reference an existing `trace_id` | `app.services.contracts.event_contract.check_lineage_compatibility` |
| Event-level lineage check | `list[LineageEvent]` with `event_id`, `trace_id`, `parent_id` | `LineageReport` | Missing `event_id`, missing `trace_id`, missing parent `event_id`, parent/child trace mismatch | `app.services.validation.event_lineage.validate_event_lineage` |
| Cross-module consistency | Decision ids, execution ids, risk-result map, event-bus record map, lineage graph map | `ConsistencyResult` per check | Decision missing risk result, execution missing event-bus record, decision missing lineage graph node, event contract violations adapted into consistency failures | `app.services.validation.cross_module_consistency.check_*` |
| Decision output | `object` decision and `object` validation context | `ValidationResult` with `allowed`, `reasons`, `warnings` | Contract denial becomes `reasons`; pre/runtime denials are currently normalized as warnings in shadow mode | `app.services.validation.core.ValidationCore.evaluate` |

## Execution blind spots

- Coverage is not correctness: `check_risk_coverage`, `check_event_bus_coverage`, and `check_lineage_coverage` verify key presence only; they do not validate payload correctness or semantic causality.
- Trace-level and event-level lineage are intentionally divergent: trace envelope compatibility and event ancestry are validated by separate projections and are not unified end-to-end.
- `ValidationCore.evaluate` normalizes contract/pre/runtime outputs but does not itself prove that upstream raw event envelope validation already ran.
- `check_event_contract` adapts raw event schema failures into `ConsistencyResult`, but does not invoke event-level ancestry validation.
- The synthetic pilot trace can prove pipeline completeness and deterministic trace integrity, not trading/business correctness.

## CONTROLLED_PILOT_READINESS_CRITERIA v1

- Full validation pipeline executes end-to-end for a synthetic lifecycle trace.
- No module bypasses `ContractRegistry` for `CONTRACT_RULES` interpretation.
- Lineage divergence remains explicit: trace-level envelope linkage is not silently merged with event-level ancestry.
- All validation layers produce deterministic output shapes for the same synthetic trace.
- Cross-module consistency checks execute and report deterministic coverage status.
- Final decision output is produced through `ValidationCore.evaluate`.
