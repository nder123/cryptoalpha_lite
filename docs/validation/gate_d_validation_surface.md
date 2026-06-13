# Gate D Validation Surface

## System diagram

```text
contracts.py (DATA ONLY)
        |
        v
ContractRegistry.evaluate()
        |
        v
ValidationCore.evaluate()
        |
        +--> Lineage Integrity Layer
        |      - event_contract: TRACE_LEVEL envelope semantics
        |      - event_lineage: EVENT_LEVEL ancestry semantics
        |
        +--> Cross-System Consistency Layer
               - cross_module_consistency.check_*
```

No module outside `ContractRegistry` is allowed to interpret contract semantics.

## Three-layer model

### 1. Contract Execution Layer

| Surface | Input type | Output type | Semantic responsibility | Status |
| --- | --- | --- | --- | --- |
| `ContractRegistry.evaluate` | `Mapping[str, object]` decision payload | `dict[str, object]` with `valid` and `violations` | The only interpreter of `CONTRACT_RULES`. | production-critical |
| `ValidationCore.validate_contracts` | `object` event for injected legacy contracts | `object` from injected legacy contract or `None` | Deprecated compatibility shim; not used by `ValidationCore.evaluate`. | legacy |

### 2. Lineage Integrity Layer

| Surface | Input type | Output type | Semantic responsibility | Status |
| --- | --- | --- | --- | --- |
| `event_contract.validate_event` | `Dict[str, Any]` raw event | `list[str]` violations | Validates raw event envelope fields and primitive field types. | internal-only |
| `event_contract.validate_batch` | `Sequence[Dict[str, Any]]` raw events | `Dict[int, list[str]]` violations by index | Batch wrapper for raw event envelope validation. | internal-only |
| `event_contract.check_lineage_compatibility` | `Sequence[Dict[str, Any]]` raw events | `list[str]` violations | TRACE semantics: `parent_id` links to trace-level graph boundary, not event ancestry. | internal-only |
| `event_lineage.validate_event_lineage` | `list[LineageEvent]` | `LineageReport` | EVENT semantics: validates strict event-id ancestry plus trace consistency. | internal-only |
| `event_lineage.assert_event_lineage` | `list[LineageEvent]` | `None` or `AssertionError` | Assertion wrapper over event-level lineage validation. | internal-only |

### 3. Cross-System Consistency Layer

| Surface | Input type | Output type | Semantic responsibility | Status |
| --- | --- | --- | --- | --- |
| `ValidationCore.evaluate` | `object` decision, `object` context | `ValidationResult` | Orchestrates contract, pre-execution, and runtime validation results. | production-critical |
| `cross_module_consistency.check_risk_coverage` | `Sequence[str]`, `Dict[str, object]` | `ConsistencyResult` | Ensures every trade decision has a risk result. | internal-only |
| `cross_module_consistency.check_event_bus_coverage` | `Sequence[str]`, `Dict[str, object]` | `ConsistencyResult` | Ensures every execution event has an event-bus record. | internal-only |
| `cross_module_consistency.check_lineage_coverage` | `Sequence[str]`, `Dict[str, object]` | `ConsistencyResult` | Ensures every gate decision appears in the event-level lineage graph. | internal-only |
| `cross_module_consistency.check_event_contract` | `Sequence[Dict[str, Any]]` | `ConsistencyResult` | Adapts raw event contract violations into cross-module consistency results. | internal-only |

## Gate D boundary rule

`CONTRACT_RULES` are data only. `ContractRegistry.evaluate` is the only allowed interpreter of those rules. Orchestrators may call the registry and normalize its result, but they must not parse rule fields, evaluate rule operations, or duplicate terminal contract semantics.
