# Stage 1 Truth Separation v1

**Status:** stabilization document (precision fix, not new layer)
**Date:** 2026-05-24
**Authority under:** every prior Stage 1 freeze document
**Adds no new claims.** Re-frames the boundaries of three already-existing
truths so they cannot be conflated by future work.

This is a deliberately small document. It exists because the governance
stack has grown enough that the **distinct domains of truth** inside it
need to be named explicitly. Without this separation, future PRs (and
future stages) risk applying the right mechanism to the wrong domain.

---

## 0. Honest framing

The previous documents (`stage_evolution_protocol_v1.md` and
`stage_transformation_algebra_v1.md`) used some language — "algebra",
"closure", "theorem" — that is **stronger than what the system actually
is**. The system is in fact:

```
typed mutation grammar over versioned system snapshots
+ CI-enforced external oracle
+ prose governance protocol
```

— **not** a mathematically closed algebra in the strict sense.

This document does not retract those earlier documents. It clarifies their
*scope* so they can be read as engineering artifacts, not as mathematical
claims. Both prior documents remain frozen and authoritative within the
domain stated in §1.

---

## 1. The three truths

Inside this repository, three distinct kinds of truth coexist. Confusing
them produces drift.

### 1.1 Runtime truth

What the system does at runtime, observable in its outputs.

| Encoded in                                      | Verifier                          |
|-------------------------------------------------|-----------------------------------|
| `artifacts/runtime_health.json`                 | the watchdog process (single writer) |
| `artifacts/runtime_health_transitions.jsonl`    | the watchdog process              |
| `artifacts/trading_gate_evidence.jsonl`         | the trading gate                  |
| journald `cryptoalpha-*` streams                | each producing service            |
| HTTP responses on `:8000`                       | uvicorn / FastAPI                 |
| pytest outcomes                                 | pytest itself                     |

Runtime truth is **dynamic** and **inspectable**. It is the only truth
that an exchange or an operator interacts with directly.

### 1.2 Specification truth

What the system *claims* it does, encoded in declarative form.

| Encoded in                                              | Verifier                          |
|---------------------------------------------------------|-----------------------------------|
| every `docs/*_v1.md` Stage 1 freeze sub-document        | human review                      |
| `docs/stage1_freeze_v1.md`                              | this and `runtime.freeze_guard`   |
| `docs/stage1_freeze_manifest.json`                      | `runtime.freeze_guard`            |

Specification truth is **static** and **declarative**. It is the contract
between humans (and between PRs) about what the system is supposed to be.

### 1.3 Evolution truth

What the system is permitted to *become*, encoded as rules over how
runtime truth and specification truth may change together.

| Encoded in                                              | Verifier                          |
|---------------------------------------------------------|-----------------------------------|
| `docs/stage1_errata_workflow.md`                        | human review (PR description path)|
| `docs/stage_evolution_protocol_v1.md`                   | human review                      |
| `docs/stage_transformation_algebra_v1.md`               | human review                      |
| `runtime.freeze_guard` (when invoked on PR delta)       | CI                                |

Evolution truth is **modal**: it expresses what changes are allowed, not
what is true now or what will be true after. It is the only truth whose
authority is *ahead* of the system in time.

---

## 2. Each artifact belongs to exactly one truth

This table is normative. If a future artifact straddles two truths, it
must be split.

| Artifact                                                    | Truth          |
|-------------------------------------------------------------|----------------|
| `backend/runtime/watchdog/*.py`                             | Runtime        |
| `backend/runtime/retention/*.py`                            | Runtime        |
| `backend/runtime/timeline/*.py`                             | Runtime        |
| `backend/runtime/chaos/harness.py`                          | Runtime (test) |
| `backend/app/services/trading_gate.py`                      | Runtime        |
| `backend/app/services/runtime_health_reader.py`             | Runtime        |
| `backend/runtime/freeze_guard/*.py`                         | Spec ↔ Runtime bridge (only) |
| `docs/runtime_topology_v1.md`                               | Spec           |
| `docs/runtime_bootstrap_contract_v1.md`                     | Spec           |
| `docs/unified_health_state_machine_v1.md`                   | Spec           |
| `docs/watchdog_recovery_v1.md`                              | Spec           |
| `docs/safe_mode_enforcement_v1.md`                          | Spec           |
| `docs/retention_cleanup_v1.md`                              | Spec           |
| `docs/operational_timeline_v1.md`                           | Spec           |
| `docs/chaos_recovery_drills_v1.md`                          | Spec           |
| `docs/stage1_freeze_v1.md`                                  | Spec           |
| `docs/stage1_freeze_manifest.json`                          | Spec           |
| `docs/stage1_errata_workflow.md`                            | Evolution      |
| `docs/stage_evolution_protocol_v1.md`                       | Evolution      |
| `docs/stage_transformation_algebra_v1.md`                   | Evolution      |
| `docs/stage1_truth_separation_v1.md` (this document)        | Evolution      |
| `.github/workflows/stage1-freeze-gate.yml`                  | Evolution (CI) |

`runtime.freeze_guard` is the **only** code that crosses categories. It
reads Spec, observes Runtime, and reports a binary. It does not write to
either, and it is not part of the runtime data plane.

---

## 3. The role of `R` is now precise

`R(S) = freeze_guard.verify` was earlier described as the "identity element"
and "Reflection operator" of an algebra. Both descriptions are *evocative*
but **imprecise**. The honest description:

> `R` is an **external validation oracle** that compares Specification
> truth (the manifest) against the Runtime artifacts of a candidate PR.
> It is not a closure operator, not an algebraic identity, and not part of
> the mutation grammar. It is the **gate** between the proposed mutation
> and its admittance to the system.

Implications:

- the mutation grammar `Adm` (Extension, Specialization, ⊕, Deprecate) lives
  entirely in **Evolution truth**;
- the witness of every mutation lives in **Runtime truth** (added tests,
  added units, modified files);
- the verification that the witness matches the grammar lives in **Spec
  truth** (the manifest);
- `R` is the bridge — it does not extend any of the three. It checks
  consistency between two of them at PR-time.

This re-framing does not change any code, document, or test. It restricts
how those artifacts may be referred to in future arguments.

---

## 4. The "algebra" downgrade

`stage_transformation_algebra_v1.md` introduces five operations and labels
them an "algebra". The honest reading:

> These five operations form a **typed mutation grammar**. The grammar is
> not closed under composition with arbitrary admissibility (specifically:
> two admissible mutations may, in sequence, produce a state that needs
> manual review even if both individually pass `R`). It is therefore not
> an algebra in the strict sense. It is a **finite admissibility
> classifier** for proposed PRs.

The grammar is still useful — its enumeration cleanly separates additive
mutations (E, P, ⊕, Deprecate) from forbidden non-operations (Remove,
Substitute-weaker, ShiftDomain, Erode). That separation has engineering
value independent of the mathematical label.

After this document, references to "the algebra" should be read as
"the mutation grammar" everywhere. The earlier document keeps its name
for stability of references (renaming the file would itself violate the
mutation grammar).

---

## 5. The Erode class — re-stated precisely

The "semantic equivalence drift" gap acknowledged in
`stage_transformation_algebra_v1.md §6.4` is more precisely:

> **Erode** is a class of *witnessable* mutations (test names, file paths,
> imports, schemas all unchanged) whose **runtime semantics** is silently
> weakened — and whose detection requires comparing runtime *behavior*
> across versions.

Erode is therefore a **Runtime-truth phenomenon** with no Spec-truth
projection that the current Freeze Guard can examine. Closing it requires
either:

- a Runtime-truth diff mechanism (e.g., recorded golden traces compared
  across versions); or
- property-based testing whose properties are themselves part of Spec truth
  (so Erode would manifest as a property failure).

Both are **out of scope** for v1. Listed here only to make the gap
unambiguous.

---

## 6. What this document forbids

The following claims must not appear in any future PR description, freeze
document, or commit message **without** an explicit re-entry:

- "the system is mathematically closed";
- "PR space = algebraic closure space" (it is not — see
  `stage_transformation_algebra_v1.md §6` and §3 of this document);
- "the freeze guard is an algebraic operator";
- "Erode is detected by CI" (it is not).

Each of these is a true statement *about an idealization* of the system,
not about the system. Conflating them with the system's actual capabilities
produces drift the next reader must un-tangle.

---

## 7. What this document permits

A PR that:

- adds a Runtime artifact AND its Spec entry AND a witness test, in one
  change set, satisfying the existing Freeze Guard, IS admissible by the
  mutation grammar (Extension `E_x`).
- adds a stronger condition to an existing test, with no Spec-text edit,
  IS admissible (Specialization `P_{i,c}`).
- introduces a Stage 2 with disjoint domain, AND its own manifest, AND its
  own gate, IS admissible (Composition `⊕`).
- merely re-runs CI on a no-op PR IS admissible (`R` returns `valid`).
- deprecates a surface with target removal stage and successor in place, IS
  admissible (`Deprecate`).

Every other shape requires either:

- a re-entry against the mutation grammar
  (`stage_transformation_algebra_v2.md`); or
- a re-entry against the protocol (`stage_evolution_protocol_v2.md`); or
- a re-entry against the kernel contract (a separate domain entirely).

---

## 8. Stabilization stance

After this document, **Stage 1 is stabilized**. The next two operator
actions are:

1. `git tag stage1.freeze.v1` — anchors this entire stack at the current
   commit.
2. Branch protection on `main` requiring the `stage1-freeze-gate` workflow
   to pass.

No further governance documents are required for Stage 1. The next
admissible structural change is Stage 2 entry per
`stage_transformation_algebra_v1.md §12`, applied via `⊕`.

---

## 9. End of stabilization

The repository now distinguishes:

- what it does (Runtime truth);
- what it claims (Specification truth);
- what it is permitted to become (Evolution truth);

— and locates each existing artifact in exactly one of those categories.
The Freeze Guard occupies the only sanctioned bridge. The mutation grammar
classifies admissible PRs. The protocol gives the prose justification.
The algebra document gives the enumeration.

No layer above this is required. The system has stopped growing meta.
