# Stage Transformation Algebra v1

**Status:** frozen formal algebra
**Date:** 2026-05-24
**Authority over:** every admissible mutation of any frozen Stage
**Authority under:** `kernel_contract_freeze_v1.md`, `docs/stage_evolution_protocol_v1.md`
**Position in stack:** one level above the Stage Evolution Protocol; it
*formalizes* the prose rules of that protocol as an operation set with
algebraic properties.

This is a **formal artifact**. It defines the carrier set, the operations,
their closure properties, the forbidden non-operations, and the relation to
existing freeze documents. It does not implement anything. It declares
what *can* be implemented in a way that is admissible under the protocol.

After this document is in place, every PR touching a frozen Stage MUST be
classifiable as either (a) an application of an operation defined herein,
or (b) a re-entry against this algebra per §9.

---

## 0. Why this document exists

`stage_evolution_protocol_v1.md` declares — in prose — that stages compose
additively, cannot delete each other, and obey domain authority. That prose
is sufficient for humans. It is **not sufficient** as a constraint:

- "additive" is informal — additive *over what algebra*?
- "compose" is informal — under which composition law?
- "cannot delete" is informal — what is the formal absence-of-deletion property?

This algebra answers those three questions. The Stage Evolution Protocol
becomes a *consequence* of this algebra, not a parallel rule set.

---

## 1. Carrier set

Let `𝓢` be the set of **admissible Stages**. Each `S ∈ 𝓢` is a tuple:

```
S = (A_S, I_S, Σ_S, U_S, D_S, T_S, M_S)
```

where:

| Symbol | Name        | Type                                    | Bounded by                |
|--------|-------------|-----------------------------------------|---------------------------|
| `A_S`  | axioms      | set of non-negotiable structural facts  | `stageN_freeze_vN.md §2`  |
| `I_S`  | invariants  | set of mechanically-verifiable claims   | `stageN_freeze_vN.md §6`  |
| `Σ_S`  | schemas     | set of versioned data contracts         | `stageN_freeze_vN.md`     |
| `U_S`  | surfaces    | set of public APIs (HTTP / CLI / files) | `stageN_freeze_vN.md`     |
| `D_S`  | domain      | set of repo paths owned exclusively     | `stageN_freeze_vN.md §1`  |
| `T_S`  | test count  | minimum cardinality of witness tests    | `stageN_manifest §test_count_baseline` |
| `M_S`  | manifest    | the executable encoding of A,I,Σ,U,D,T  | `stageN_freeze_manifest.json` |

`𝓢` is **non-empty** and **monotone**: Stage 1 ∈ 𝓢 today. Future stages
extend 𝓢 by adding members, never by replacing or shrinking existing
members.

---

## 2. Operations on `𝓢`

Five operations are admissible. Every other mutation is **outside the
algebra** (see §6).

### 2.1 `E_x(S)` — Extension by claim `x`

Adds a new claim `x` of class Axiom / Invariant / Schema / Surface to `S`.

```
E_x : 𝓢 × Claim → 𝓢
E_x(S) = S' where:
  - A_{S'} = A_S ∪ {x}    if class(x) = Axiom
  - I_{S'} = I_S ∪ {x}    if class(x) = Invariant
  - Σ_{S'} = Σ_S ∪ {x}    if class(x) = Schema
  - U_{S'} = U_S ∪ {x}    if class(x) = Surface
  - all other components of S' equal those of S
```

**Preconditions for admissibility:**

- `x` does not contradict any existing element of `A_S ∪ I_S`;
- `class(x) = Schema` requires `x` to be a new version of an existing
  schema OR a wholly new schema; replacing an existing schema is NOT
  Extension;
- `class(x) = Surface` requires `x` to be a new endpoint / CLI / file; if
  `x` superficially matches an existing surface, the operation is
  Specialization (§2.2), not Extension;
- `T_{S'} ≥ T_S` (test count never shrinks; new claim needs at least one
  witness test).

**Maps to:** Stage 1 amendment path (per `stage_evolution_protocol_v1 §3.2`)
or in-stage errata that adds a witness.

### 2.2 `P_{i,c}(S)` — Specialization of invariant `i` by condition `c`

Strengthens an existing invariant `i ∈ I_S` with an additional condition `c`
such that `i ∧ c ⇒ i`. Effectively, the new invariant is at least as strong.

```
P_{i,c}(S) = S' where:
  - I_{S'} = (I_S \ {i}) ∪ {i ∧ c}
  - all other components equal those of S
  - constraint: i ∧ c ⇒ i  (specialization, never relaxation)
```

**Preconditions:**

- `i ∈ I_S`;
- `c` strengthens (or is logically equivalent to) `i`; it does not weaken it;
- a witness test is added or existing test is strengthened — never weakened
  (the semantic-equivalence-drift blind spot acknowledged in
  `stage_evolution_protocol_v1 §9` lives here; closing it is a v2 problem).

**Maps to:** errata path that tightens behavior without changing surface.

### 2.3 `R(S)` — Reflection

Reflection produces the manifest projection of `S` and verifies the
declarative truth equals the observed truth on the live repo. Pure read.

```
R : 𝓢 → {valid, violation_report}
R(S) = freeze_guard.verify against M_S
```

`R(S) = valid` is the **CI gate's** definition of admissibility on every
PR. A violation report from `R(S)` is the negation of any PR's claim to
have applied an algebra operation.

**Property:** Reflection is **idempotent** and **side-effect free**. It is
the algebra's mechanism for binding declarative and observed truth.

### 2.4 `S₁ ⊕ S₂` — Domain composition

Composes two stages with disjoint domains into a joint operating
configuration. **Does not produce a new stage.** Produces a runtime in
which both stages' Freeze Guards run as gates.

```
⊕ : 𝓢 × 𝓢 → Configuration
S₁ ⊕ S₂ admissible iff:
  D_{S₁} ∩ D_{S₂} = ∅                       (disjoint domains)
  A_{S₁} ∪ A_{S₂} is internally consistent  (no axiom contradiction)
  I_{S₁} ∪ I_{S₂} is internally consistent  (no invariant contradiction)
```

Symmetric and associative: `(S₁ ⊕ S₂) ⊕ S₃ = S₁ ⊕ (S₂ ⊕ S₃)`.

**Maps to:** Stage 2 entry (Stage 1 ⊕ Stage 2). The "co-existing constraint
systems" of `stage_evolution_protocol_v1 §4.1` is exactly this operation.

### 2.5 `Deprecate_{u, t}(S)` — Surface deprecation

Marks a surface `u ∈ U_S` as `deprecated` with target removal stage `t`
(where `t > current_stage_index`). The surface remains in `U_S` for the
deprecation window.

```
Deprecate_{u, t}(S) = S' where:
  - U_{S'} = (U_S \ {u}) ∪ {u^{deprecated, removal=t}}
  - the labelled element behaves identically at runtime
  - removal of `u` from U_{S'} is admissible only at stage t, only if
    a successor surface u' has been Extended in stage t' where current < t' < t.
```

**Maps to:** `stage_evolution_protocol_v1 §5`. The "successor must outlive
deprecation" rule is the algebra's definition of admissible removal: it is
**not** a primitive operation. There is no `Remove(u)`. Removal is the
*final scheduled step* of `Deprecate`, and it executes only when its own
preconditions hold.

---

## 3. Closure laws

Let `Adm ⊆ {E, P, R, ⊕, Deprecate}` be the admissible operations on `𝓢`.

### 3.1 Closure under composition

For any finite sequence `(o₁, …, oₙ) ∈ Adm*` and any admissible inputs:

```
o₁ ∘ o₂ ∘ … ∘ oₙ produces an admissible result
```

Closure means: *every* admissible PR is the application of some finite
sequence of operations from `Adm`. There is no admissible PR outside this
closure.

### 3.2 Idempotence of pure operations

- `R(R(S)) = R(S)` — Reflection is idempotent.
- `E_x(E_x(S)) = E_x(S)` — adding the same claim twice is a no-op.

### 3.3 Commutativity (when disjoint)

If `x` and `y` are claims of disjoint substance (e.g. one is an Invariant
about Stage 1's watchdog, the other is a Schema for Stage 2's federation
event):

```
E_x(E_y(S)) = E_y(E_x(S))
```

This makes PRs that touch unrelated parts of the manifest order-independent
in the algebra. The CI gate enforces this implicitly: it runs the full
Reflection regardless of PR order.

### 3.4 Non-cancellation

For every pair of admissible operations `o, o'`, there is **no** `o'` such
that `o'(o(S)) = S`. Equivalently:

```
the algebra has no inverse element
```

This is the formal statement of "no destructive evolution". Any operation
that produces `S' = S` modulo bookkeeping is `R` (Reflection); any
operation that *appears* to reduce S is outside the algebra (§6).

---

## 4. Identity element

The **identity** of the algebra on a Stage `S` is `R(S)` — Reflection that
returns `valid`. Equivalently, an empty operation sequence is identity:

```
Id(S) = S
∅-sequence ∘ S = S
R(S) = valid ⟹ S admissible
```

Identity is observable: every successful CI run on `main` is an instance of
`Id`. No actual mutation occurred, the system stays in `𝓢`, the freeze is
preserved.

---

## 5. Properties summary table

| Operation                | Acts on        | Preserves                                       | Reversible? |
|--------------------------|----------------|-------------------------------------------------|-------------|
| `E_x`                    | A, I, Σ, U     | all existing claims; test count                 | No (§3.4)   |
| `P_{i,c}`                | I              | all axioms; semantic implication `(i ∧ c) ⇒ i`  | No          |
| `R`                      | (read only)    | everything                                       | Yes (no-op) |
| `⊕`                      | configuration  | all axioms / invariants of both operands         | No          |
| `Deprecate_{u,t}`        | U              | u operational behavior during window             | No          |

**Reversibility column is the formal counterpart of §3.4.**

---

## 6. Forbidden non-operations

The following are **not in the algebra**. They cannot be written as any
sequence in `Adm*`:

### 6.1 `Remove_x(S)` — claim removal

There is no operation that produces `S'` with strictly smaller
`A_{S'} / I_{S'} / Σ_{S'} / T_{S'}`. Schema and surface removal happens
only as the scheduled end of `Deprecate` after its preconditions hold —
which is itself the *application* of `Deprecate`, not a separate
`Remove`.

### 6.2 `Substitute_{i, j}(S)` — invariant replacement

There is no operation that swaps `i ∈ I_S` for `j` unless `i ∧ ¬j` is
consistent (i.e., `j` is a Specialization of `i`, in which case use
`P_{i,c}` with `c = j ⇒ i`). Substituting `i` with a *weaker* `j` is
forbidden.

### 6.3 `ShiftDomain_{p, S₁ → S₂}(p)` — authority transfer

There is no operation that moves a path `p ∈ D_{S₁}` to `D_{S₂}` once
both stages are frozen. Domain authority is set at stage entry (the act
of becoming an operand of `⊕`) and never reassigned thereafter.

### 6.4 `Erode_x(S)` — silent weakening

There is no operation that preserves the *name* of a claim while
weakening its content. This is the **semantic equivalence drift** problem.
The algebra does not contain such an operation; the **CI gate cannot
detect** it for free; closing this gap is the only honest reason to
re-enter the algebra per §9.

---

## 7. The Stage Evolution Protocol as a theorem

`stage_evolution_protocol_v1` becomes a derived corollary of this algebra.

### 7.1 Protocol §3.3 ("Stage N+1 may NOT relax inherited axiom") follows from:

- `Remove_x` ∉ `Adm` (§6.1);
- `Substitute_{i, j}` with `j` weaker than `i` ∉ `Adm` (§6.2);
- ⊕ preserves both operands' axiom sets (§2.4).

### 7.2 Protocol §4.1 ("multiple stages co-exist") is the existence of `⊕`.

### 7.3 Protocol §4.3 ("cross-stage consumption read-only by default") is a
*consequence* of domain disjointness: writes to `D_{S₁}` from `D_{S₂}` would
require `ShiftDomain`, which is ∉ `Adm` (§6.3).

### 7.4 Protocol §5 (surface deprecation) is the operational definition of
`Deprecate_{u,t}` (§2.5).

### 7.5 Protocol §9 (semantic equivalence drift) is exactly §6.4 above —
acknowledged as outside the algebra v1.

Therefore the Protocol does not need separate enforcement. The Freeze Guard
already enforces the manifest; the manifest is `M_S`; the manifest verifies
`R(S)`; the algebra constrains which `S'` can replace `S`. The Protocol is
the **proof** that this enforcement is sufficient; the algebra is the
**theory** the proof inhabits.

---

## 8. What this algebra does NOT define

- **Strategy plane evolution** (RL policy mutation, ML, signal logic). These
  live in `D_{S₁}^c` (outside Stage 1's domain) and either join a future
  stage via `⊕` or remain ungoverned. The algebra is silent on them.
- **The kernel plane** (`atp/`, `backend/stress/`). It is permanently
  outside every `D_S` for `S ∈ 𝓢`. Its evolution is governed by
  `kernel_contract_freeze_v1.md` independently.
- **Test semantics** beyond cardinality. `T_S ≥ T_{S\prior}` is enforced; the
  *meaning* of any individual test is not in the algebra (§6.4 is the
  acknowledgment).
- **Time.** No operation has a temporal aspect. Cycles in `Deprecate` are
  bookkeeping, not algebra.

---

## 9. Re-entry against the algebra

Same shape as the Protocol's re-entry rule, but at one higher level.

### 9.1 Required for any of:

- introducing an operation that produces `S' < S` (any kind of removal that
  is not a `Deprecate` final step);
- introducing an authority transfer (`ShiftDomain` becomes admissible);
- closing the semantic-equivalence-drift gap as an in-algebra operation
  (would require formal trace-equivalence verification — heavy);
- defining `⊕` for stages with non-disjoint domains (would mean stages can
  overlap — relaxes A2 of Stage 1 and § 4.2 of Protocol).

### 9.2 Procedure

1. New file `docs/stage_transformation_algebra_v2.md` per the same shape as
   this document. v1 file remains; v2 supersedes for new mutations only.
2. `stage_evolution_protocol_v2.md` and updated Freeze Guards are
   consequential, not prerequisite.
3. The kernel contract is unaffected; no operational stage is rewritten.

### 9.3 What re-entry is NOT for

- adding a new operation that *strengthens* the algebra (e.g., a
  `StrongerSpecialization`) — that is itself an Extension of `Adm` and is
  admissible *within v1* as long as no existing operation is weakened. The
  algebra is itself a Stage in this respect; v1 is monotone.

---

## 10. The complete governance stack (formal)

```
kernel_contract_freeze_v1.md            kernel plane axioms
        │
        ▼  (orthogonal to everything below)
stage1_freeze_v1.md                     operational substrate (S₁)
        │
        ▼
stage1_freeze_manifest.json             M_{S₁}
        │
        ▼
runtime.freeze_guard                    enforces R(S₁) on CI
        │
        ▼
stage_evolution_protocol_v1.md          prose protocol
        │
        ▼
stage_transformation_algebra_v1.md      ← THIS DOCUMENT
        │                               formal operation set Adm = {E, P, R, ⊕, Deprecate}
        │                               closure laws; forbidden ops; identity
        ▼
(future stages must apply only Adm to enter 𝓢)
```

After this point the repository's mutation surface is **formally defined**:

```
admissible PR := finite sequence of operations from Adm,
                 each precondition satisfied,
                 R(S_final) = valid
```

The Freeze Guard mechanizes the last condition. The Protocol mechanizes the
preconditions in prose. This algebra mechanizes the *form* of admissible
PRs as elements of `Adm*`.

---

## 11. Lock-in

After merge, the following are byte-stable:

- the operation set `Adm = {E, P, R, ⊕, Deprecate}`;
- the carrier set `𝓢` (Stages exist; new ones enter by `⊕`, none leave);
- the four forbidden non-operations (Remove, Substitute-weaker, ShiftDomain, Erode);
- non-cancellation (§3.4) — the algebra has no inverse;
- identity = Reflection.

Adding a new admissible operation is itself an `E_x` on this document (a
new section §2.6, §2.7, …). Removing one is forbidden — it would require
§9 re-entry.

---

## 12. End of algebra v1

The repository has now graduated from "system with constraints" to "system
whose admissible mutations form a closed algebra". Every future PR maps to
an element of `Adm*` and is verified by `R`. Drift outside the algebra is
either rejected by CI (structural classes) or acknowledged as v1 blind
spot (semantic equivalence — §6.4).

Stage 2, when it arrives, will be:

```
S₂ = E_*(E_*(...E_*(∅)...))    ⊕    S₁
```

— a stage built by Extension over an empty initial stage, then composed
with Stage 1 via `⊕`. Its admissibility will be a single Reflection on the
joint configuration `S₁ ⊕ S₂`.

This is what "additive only" means, precisely.
