# Stage 1 Errata Workflow v1

**Status:** frozen procedure
**Date:** 2026-05-24
**Authority:** `docs/stage1_freeze_v1.md §10`, `docs/stage1_freeze_manifest.json`
**Enforcement:** `.github/workflows/stage1-freeze-gate.yml`, `runtime.freeze_guard`

This document is the *operational procedure* for modifying anything inside
the Stage 1 frozen surface. The freeze itself is declarative; this is how
changes traverse it without violating the contract.

---

## 0. Hard rule

> If a PR fails `runtime.freeze_guard verify` or drops a Stage 1 test, it
> does NOT merge. No exceptions.

The CI gate runs `freeze_guard verify` and the full Stage 1 test surface on
every PR and on every push to `main`. A red gate is a hard block.

---

## 1. Three legal change paths

| Path                    | When to use                                                                                  | Required artifacts                                                                                                                                            |
|-------------------------|----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **A. Errata**           | A small, additive fix that preserves every axiom + invariant.                                | (1) `## Errata` section in the affected sub-document. (2) Test(s) added if behavior surface changed. (3) `freeze_guard verify` green. (4) test count ≥ baseline. |
| **B. Stage 1 amendment**| Behavior surface must grow (new gate site, new probe, new endpoint, new retention rule).     | (1) Bump affected sub-doc to `vN+1`. (2) Update §1 of `stage1_freeze_v1.md`. (3) Update `stage1_freeze_manifest.json` (new assertion + new test count). (4) New tests. |
| **C. Stage 2 entry**    | An axiom in `stage1_freeze_v1.md §2` must be relaxed OR an invariant in §6 must be relaxed.  | (1) New top-level document `docs/stage2_freeze_v1.md`. (2) Co-exists with Stage 1 freeze; does not supersede it. (3) New CI workflow.                          |

Path A is the **default**. Path C is **rare and expensive**. If unsure, use A
and the gate will tell you when B is required.

---

## 2. Path A — Errata (minimal procedure)

### 2.1 Checklist

- [ ] change is additive or strictly preserves observable behavior;
- [ ] no axiom (A1..A5) is touched;
- [ ] no invariant (I-Stage1-1..8) is touched;
- [ ] no entry in `frozen_documents` is renamed or deleted;
- [ ] no `structural_assertions` clause requires a manifest update;
- [ ] each test file count is ≥ its manifest baseline;
- [ ] `poetry run python -m runtime.freeze_guard verify` returns rc=0 locally;
- [ ] an `## Errata` block is appended to the affected sub-document with date
      + one-paragraph description + commit/PR reference.

### 2.2 Example errata block

```markdown
## Errata

### 2026-05-30 — clarified retention "never silent" wording

Per ambiguity in §6.2: replaced "every prune writes one journald line"
with "every batch prune writes one summary journald line". Behavior was
already a batch summary; this is a documentation-only clarification.
PR #142.
```

---

## 3. Path B — Stage 1 amendment

### 3.1 When to use

- adding a new gate site (e.g. `position_manager.open_position`);
- adding a new probe (e.g. P11);
- adding a new endpoint;
- adding a new retention rule;
- adding a new drill class;
- adding a new timeline source.

### 3.2 Required changes

1. Bump affected sub-document version (e.g. `safe_mode_enforcement_v1.md` →
   amend in place, label the new section "v1.1") or rename to `_v2.md` if the
   contract is materially extended.
2. Update `stage1_freeze_v1.md §1.1` (and §1.2/§1.3 as needed) to reflect
   the new artifact.
3. Update `stage1_freeze_manifest.json`:
   - add new `structural_assertions` entry tied to relevant axiom/invariant;
   - bump corresponding test-count baseline upward;
   - update `minimum_total`.
4. Add test cases that prove the new contract holds.
5. Re-run gate locally; ensure rc=0.

### 3.3 What NOT to do under Path B

- do NOT change `expected_members` of an `enum_members` assertion (that's
  a Path C change — it relaxes the state set);
- do NOT remove entries from `FORBIDDEN_AUTORESTART` or
  `FORBIDDEN_DIRECT_TRANSITIONS`;
- do NOT lower any test-count baseline.

---

## 4. Path C — Stage 2 entry

### 4.1 When required

Any of:

- relaxing axiom A1 (e.g. moving supervisor into a container);
- relaxing axiom A2 (e.g. multi-writer for `runtime_health.json`);
- relaxing axiom A3 (e.g. hysteresis on P10);
- relaxing axiom A4 (auto-exit from SAFE_MODE);
- relaxing axiom A5 (unbounded retention pass);
- multi-instance / federation;
- exceeding the §8 hardware envelope.

### 4.2 Required artifacts

1. `docs/stage2_freeze_v1.md` — new top-level freeze with its own axiom set,
   invariants, test surface, manifest. It MUST explicitly state which
   Stage 1 axiom is relaxed and how.
2. `docs/stage2_freeze_manifest.json` — its own assertion set; can reference
   Stage 1 manifest by inclusion but does not modify it.
3. `.github/workflows/stage2-freeze-gate.yml` — new gate.
4. Stage 1 freeze remains untouched. Both gates run in parallel.

### 4.3 What this means in practice

Stage 2 is **not a Stage 1 upgrade**. They co-exist as parallel constraint
systems. A repo branch may opt into Stage 2 explicitly; main may continue
under Stage 1 indefinitely.

---

## 5. Gate machinery

### 5.1 Local pre-commit

Run locally before pushing:

```bash
cd backend
poetry run python -m runtime.freeze_guard verify
poetry run pytest tests/test_freeze_guard.py tests/test_stress_harness.py \
                  tests/test_watchdog_*.py tests/test_safe_mode_*.py \
                  tests/test_retention.py tests/test_chaos_drills.py \
                  tests/test_timeline.py
```

Both must return rc=0.

### 5.2 CI

`.github/workflows/stage1-freeze-gate.yml`:

- runs on every PR and every push to `main`;
- emits `freeze_report.json` as a workflow artifact;
- fails the build (and blocks merge with the appropriate branch protection
  rule) on any non-zero exit.

### 5.3 Violation codes

The guard emits stable violation codes so PR review can pattern-match:

| Code              | Meaning                                                        |
|-------------------|----------------------------------------------------------------|
| `FG-DOC-MISSING`  | a frozen document is missing                                   |
| `FG-ENUM-1`       | enum members differ from manifest expectation                  |
| `FG-PAIR-1`       | required pair missing from a set-of-pairs                      |
| `FG-SET-1`        | required member missing from a set                             |
| `FG-SET-EX-1`     | exact-set assertion failed                                     |
| `FG-TUPDC-1`      | dataclass-tuple field-value superset assertion failed          |
| `FG-CONST-1`      | constant value differs from manifest expectation               |
| `FG-TESTS-1`      | per-file test count regressed                                  |
| `FG-TESTS-TOTAL`  | aggregate test count below minimum                             |
| `FG-KIND-UNKNOWN` | manifest specifies an unknown assertion kind                   |
| `FG-LOAD-{1..6}`  | failed to import / load the asserted attribute                 |
| `FG-MANIFEST-LOAD`| manifest itself unreadable                                     |

A PR description that triggers any of these MUST cite which path (A/B/C) it
intends to traverse.

---

## 6. Boundaries (preserved by this document)

This errata workflow does NOT modify:

- the freeze documents (`stage1_freeze_v1.md`, sub-docs);
- the manifest (`stage1_freeze_manifest.json`);
- the freeze guard code (`backend/runtime/freeze_guard/`);
- any production code or tests.

It only declares the **procedure** that the gate enforces.

---

## 7. End of procedure

After this document is in place, the Stage 1 freeze is no longer a textual
artifact. It is a **runtime-active constraint system** with three sanctioned
mutation paths and a CI gate that refuses every other path.
