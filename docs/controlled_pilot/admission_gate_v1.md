# Controlled Pilot Admission Gate v1

## Admission status definition

The system is `READY FOR CONTROLLED PILOT EXECUTION` only when all hard
requirements pass and soft observability requirements are known.

## A. Hard requirements

- Full execution trace completes without interruption.
- `ContractRegistry` is the only contract interpreter.
- Lineage divergence remains explicit and tested.
- No module bypasses the `ValidationCore.evaluate` orchestration path for final
  decision semantics.
- All tests in the controlled pilot readiness suite pass.

## B. Soft requirements: observability

- Trace completeness logging exists.
- Failure modes are classified.
- Cross-module consistency reports are generated.

## C. Failure classification model

| Classification | Meaning | Admission impact |
| --- | --- | --- |
| `BLOCKER` | A hard requirement failed or the readiness suite cannot complete. | Not ready |
| `DEGRADED` | A soft observability requirement is missing or partial. | Ready only with explicit operator acknowledgement |
| `OBSERVATIONAL ONLY` | Informational signal that does not affect pilot admission. | Ready |

## EXECUTION INTERPRETATION BOUNDARY

No module outside `ValidationCore` may define final decision semantics.

`ValidationCore.evaluate` is the orchestration boundary for final validation
decision output. Downstream modules may consume its result, and upstream modules
may provide deterministic validation inputs, but final decision semantics must
not be redefined outside this boundary.

## Controlled pilot readiness suite

The readiness gate is checked by:

```bash
python scripts/check_controlled_pilot_readiness.py
```

The script emits a single JSON object:

```json
{
  "ready": true,
  "blockers": [],
  "warnings": []
}
```
