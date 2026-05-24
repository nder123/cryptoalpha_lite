# Stage Evolution Protocol v1

**Status:** frozen meta-protocol
**Date:** 2026-05-24
**Authority over:** every future `docs/stageN_freeze_v*.md`
**Authority under:** `kernel_contract_freeze_v1.md` (kernel) and
`docs/stage1_freeze_v1.md` (operational)
**Enforcement:** human review + `runtime.freeze_guard` (Stage 1 only — Stage 2+
gates extend it, never replace)
**Purpose:** declare the rules under which **new stages** may be added to this
repository **without breaking** the frozen substrate or the Freeze Guard.

This is a **meta-protocol**. It does not describe Stage 2. It describes the
shape any Stage 2 (or 3, 4, …) is permitted to take. It is itself frozen and
versioned: changes to the protocol require a new protocol version, not an
in-place edit.

---

## 0. Why this document exists

After `stage1_freeze_v1.md` and `stage1_freeze_manifest.json` made Stage 1 a
runtime-active constraint system, the next architectural risk is no longer
"can we build features" — it is:

```
how does a new stage extend the system without breaking the freeze?
```

If Stage 2 is built as a Stage 1 superset, the freeze becomes erodable —
gradually relaxed under the cover of "improvements". If Stage 2 is built as
a Stage 1 replacement, the system loses its earned invariants. Both are
unacceptable.

This protocol declares the third path: **stages compose by domain, not by
generation**. Stage N+1 introduces a new invariant domain *over* the frozen
substrate — never instead of it.

---

## 1. Definitions

- **Frozen substrate.** The byte-equal state of every artifact named in any
  prior `stageN_freeze_vN.md §1` (frozen documents, code modules, manifests,
  test counts, integration points, supervisor units, scripts).
- **Stage.** A coherent set of contracts, invariants, axioms, and tests
  delivered as one freeze document plus its manifest. Stages are **named**
  and **numbered**. Numbering is monotone and total.
- **Stage axiom.** A non-negotiable structural property of a stage. Encoded
  in `stageN_freeze_vN.md §2` (or equivalent). Stage 1 has A1..A5.
- **Stage invariant.** A property whose verification is mechanically
  encoded — typically as a structural assertion in the manifest plus at
  least one witness test. Stage 1 has I-Stage1-1..8.
- **Domain.** The set of files, directories, modules, and runtime artifacts
  a stage claims authority over. Stage 1's domain is the operator plane:
  `backend/runtime/`, `backend/app/services/{trading_gate,runtime_health_reader}.py`,
  the relevant integration sites in `backend/app/exchange/` and
  `backend/app/services/execution_engine.py`, `ops/systemd-user/`, `scripts/`,
  the relevant `docs/`. The kernel plane (`atp/`, `backend/stress/`, lens
  lattice) is **outside** Stage 1's domain.

---

## 2. The four boundary classes (frozen)

Every claim a stage makes falls into exactly one of:

| Class           | Description                                                | Example (Stage 1) |
|-----------------|------------------------------------------------------------|-------------------|
| **Axiom**       | Architectural ground truth; cannot be relaxed in-stage     | A1 single supervisor; A4 operator-only SAFE_MODE exit |
| **Invariant**   | Mechanically verifiable property; must have a witness test | I-Stage1-2 SAFE_MODE→HEALTHY forbidden |
| **Schema**      | Versioned data contract                                    | `runtime_health_transition.v1` |
| **Surface**     | Public API exposed to consumers (HTTP routes, CLI, files)  | `GET /api/ops/health-state` |

Every freeze document lists its claims under these four headings.

---

## 3. Inheritance contract (frozen)

When a new stage is introduced, it inherits the frozen substrate verbatim.

### 3.1 What Stage N+1 inherits from Stage N (and earlier)

- every axiom (cannot be relaxed without re-entry per §6);
- every invariant (cannot be relaxed; can be specialized);
- every schema (cannot be removed; can be extended additively);
- every surface (cannot be removed without deprecation per §5).

### 3.2 What Stage N+1 may add

- new axioms in its own domain;
- new invariants over its own domain or over the inherited substrate;
- new schemas (new versions of existing schemas, or wholly new ones);
- new surfaces.

### 3.3 What Stage N+1 may NOT do

- relax or delete any inherited axiom;
- relax or delete any inherited invariant;
- delete or rename any inherited schema (additive evolution only);
- silently change the meaning of any inherited surface;
- shrink any inherited test count baseline;
- claim authority over the kernel plane (`atp/`, `backend/stress/`).

A change that requires any of the above is an **out-of-protocol** change and
must be handled per §6 (re-entry against this protocol).

---

## 4. Composition semantics

Stages compose as **co-existing constraint systems**, not as inheritance
hierarchies.

### 4.1 Multiple active stages

The repository may have multiple Stage Freeze documents simultaneously
active. The Freeze Guard for Stage 1 runs alongside the Freeze Guard for
Stage 2. Both must pass for a PR to merge.

### 4.2 Stage authority over its own domain

Each stage owns its own domain exclusively. A Stage 2 module placed inside
the Stage 1 domain is automatically subject to the Stage 1 Freeze Guard. A
Stage 1 module placed inside the Stage 2 domain is automatically subject to
the Stage 2 Freeze Guard. Authority is geographical (by path) and structural
(by manifest assertions).

### 4.3 Cross-stage consumption is read-only by default

A Stage N module may **read** outputs of a Stage M (M < N) module without
ceremony. It may NOT write into Stage M-owned artifacts unless Stage M's
freeze explicitly grants such write authority.

Example: a hypothetical Stage 2 federation layer may consume
`artifacts/runtime_health.json` (Stage 1 output) for cross-instance
reconciliation. It may NOT write that file. A1+A2 forbid it.

### 4.4 Joint invariants

A claim that spans two stages (e.g., "every Stage 2 transition must reference
a Stage 1 transition_id") is itself a Stage 2 invariant — declared in the
Stage 2 freeze manifest, witnessed by a Stage 2 test. The Stage 1 freeze
remains untouched.

---

## 5. Surface evolution (deprecation policy)

Surfaces (HTTP routes, CLIs, file schemas) MUST never be silently removed.

### 5.1 Procedure

1. Mark surface `deprecated` in the relevant freeze document with a target
   removal stage.
2. Maintain it for at least one **full** stage cycle (i.e., it must outlive
   one freeze document published after the deprecation notice).
3. Add a successor surface in the new stage.
4. Remove only after the successor has been live for the cycle window.

### 5.2 Schema deprecation

Equivalent rules for schemas. `runtime_health_transition.v1` may be
superseded by `v2` in Stage N+1; both must coexist for one full cycle;
v1 readers must continue to parse v1 records throughout.

### 5.3 No silent removal

The Freeze Guard's `path_exists` and `text_contains` assertions MUST cover
every deprecated surface throughout its deprecation window. Removing the
guard assertion before the surface is itself a contract violation per
this protocol.

---

## 6. Re-entry against this protocol

A change that violates §3.3 — relaxes an axiom, removes an invariant,
breaks a schema, or shrinks a baseline — is an **out-of-protocol change**
and follows this procedure.

### 6.1 Required artifacts

1. A new top-level document `docs/stage_evolution_protocol_v2.md` that
   explicitly states which clause of this v1 protocol is being relaxed and
   why. The v1 protocol remains in the repo unchanged; v2 supersedes only
   from the point of its merge forward.
2. Either:
   - a new freeze document compatible with v2 (this is the typical case); or
   - explicit migration of existing Stage 1 / Stage N artifacts to v2 rules
     (this is heavy — it involves rewriting frozen documents and is rarely
     justified).
3. Updates to all Freeze Guards to enforce v2 rules.

### 6.2 What re-entry is NOT for

- adding new tests (Stage 1 amendment, path B);
- adding new endpoints in a stage's own domain (Stage amendment);
- bumping a schema version additively (path B);
- adding a new stage that respects this protocol (Stage 2 entry under
  `stage1_freeze_v1.md §10.3` — does NOT require protocol re-entry).

---

## 7. Stage 2 — what it can and cannot be

This protocol cannot describe Stage 2 yet (Stage 2 has not been authored).
It can constrain its shape:

### 7.1 Stage 2 may be one of

- **federation/multi-instance.** A new domain that observes multiple Stage 1
  runtimes and reconciles divergence. Owns:
  `backend/runtime/federation/` (hypothetical). Reads Stage 1 outputs.
- **policy learning.** A new domain that learns from
  `runtime_health_transitions.jsonl` to suggest tunable changes — but cannot
  apply them without operator action.
- **operational hardening.** Disk-failure tolerance, partial corruption
  recovery, cross-runtime snapshot verification. Owns:
  `backend/runtime/integrity/` (hypothetical).
- **strategy plane.** Anything above L0 execution that is not RL/ML — e.g.,
  shadow paper-execution scoring, rule-based signal filtering. Stays
  upstream of the trading gate; the gate remains the only execution
  authority.

### 7.2 Stage 2 may NOT be

- a kernel rework (kernel is frozen by `kernel_contract_freeze_v1.md`);
- a SAFE_MODE auto-exit (relaxes A4);
- a Stage 1 Freeze Guard replacement (relaxes A2 by becoming a second
  authoritative writer of `stage1_freeze_manifest.json`);
- a multi-writer of `runtime_health.json` (relaxes A2);
- a removal of journald-as-evidence-channel (would relax I-Stage1-7
  semantics implicitly);
- a Kubernetes / orchestration deployment of the supervisor (relaxes A1).

If a need genuinely requires one of the above, the path is §6 — protocol
re-entry, not Stage 2.

### 7.3 Stage 2 entry checklist (when it happens)

- [ ] `docs/stage2_freeze_v1.md` exists and lists its axioms / invariants /
      schemas / surfaces under §2 of itself;
- [ ] `docs/stage2_freeze_manifest.json` exists with structural assertions;
- [ ] `.github/workflows/stage2-freeze-gate.yml` exists and runs alongside
      Stage 1 gate;
- [ ] every Stage 1 axiom and invariant is referenced from Stage 2 freeze
      with explicit "inherited verbatim" status;
- [ ] no inherited test count is decreased;
- [ ] no inherited surface is removed without §5 deprecation;
- [ ] Stage 2 owns a *new* domain (path-based authority);
- [ ] cross-stage joint invariants, if any, are declared in Stage 2's
      manifest, not in Stage 1's.

---

## 8. Two truths at once

The protocol formalizes the fact that this repository now operates with
**two truths simultaneously**:

| Truth                | Encoded in                                            | Authority                  |
|----------------------|-------------------------------------------------------|----------------------------|
| Declarative truth    | Freeze docs + manifests + this protocol               | Human review + freeze guards |
| Observed truth       | AST + grep + runtime checks + test outcomes            | CI                          |

A Stage Freeze is the binding between them. The Freeze Guard is the
mechanism that detects when they diverge. This protocol is the rule that
forbids one truth from unilaterally rewriting the other.

---

## 9. The remaining blind spot (acknowledged, out of scope for v1)

This protocol does not eliminate **semantic equivalence drift** —
the case where a test name, signature, and structure all stay the same but
its assertions become weaker. Detecting that requires:

- property-based testing (hypothesis); or
- runtime trace comparison across versions; or
- formal specification comparison.

All three are out of scope for v1. v1 documents the gap and leaves its
closure to a future amendment (likely as a Stage 2 invariant domain
"behavioral integrity" or as protocol v2).

---

## 10. Protocol freeze rules

- This document is `v1`. It is byte-stable from the day of merge forward.
- Changes to this protocol require a new file `docs/stage_evolution_protocol_v2.md`
  per §6.1. The v1 file is never edited.
- Stage 1 freeze documents are unaffected by anything here. They remain
  authoritative within their domain.
- Future Stage Freeze documents MUST cite this protocol by version in their
  preamble, e.g.:
  ```
  Authority: this freeze is under stage_evolution_protocol_v1.md.
  ```

---

## 11. What this protocol locks in

After merge, the following are no longer up for negotiation without §6
re-entry:

- the four-class taxonomy (Axiom / Invariant / Schema / Surface);
- inheritance is verbatim and additive only;
- multiple stages co-exist; Stage Freezes never supersede each other;
- the kernel plane (`atp/`, `backend/stress/`) is permanently outside any
  operational stage's domain;
- the Freeze Guard for Stage N never replaces — only extends — the Freeze
  Guard for Stage M < N;
- semantic equivalence drift is acknowledged as out of v1 scope.

---

## 12. End of protocol

The repository is now governed by a freeze ⟶ guard ⟶ protocol stack:

```
kernel_contract_freeze_v1   (orthogonal, never touched by operational work)
        │
        ▼
stage1_freeze_v1            (operational substrate, frozen)
        │
        ▼
stage1_freeze_manifest      (declarative truth)
        │
        ▼
runtime.freeze_guard        (enforced via CI)
        │
        ▼
stage_evolution_protocol_v1 ← THIS DOCUMENT
        │
        ▼
(future stages)             (must obey this protocol)
```

After this point, the repo has graduated from "system being built" to
"system with a meta-system". Further evolution proceeds by stages, each one
adding a new invariant domain over the frozen substrate, never inside it.
