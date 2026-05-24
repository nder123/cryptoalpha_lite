"""Retention policy table — frozen defaults.

Per docs/runtime_bootstrap_contract_v1.md §6.1 and docs/retention_cleanup_v1.md §3.

Each rule is declarative. The runner executes them in a single bounded pass.
No rule may delete data classified as audit (`audit=True`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RotationRule:
    """How a file gets rotated when it exceeds size.

    Rotation produces gzipped copies: `<file>.<n>.gz`, oldest = highest N.
    """

    path_relative: str          # repo-relative
    rotate_at_bytes: int        # rotate when current file >= this
    keep_rotations: int         # how many gz rotations to keep
    rule_id: str                # short id for journald + tests


@dataclass(frozen=True)
class DirectoryQuota:
    """Soft cap on total bytes under a directory tree."""

    path_relative: str
    cap_bytes: int
    keep_daily: int             # newest N daily-subdirs always kept
    keep_weekly: int            # plus N weekly snapshots
    keep_monthly: int           # plus N monthly snapshots
    rule_id: str


@dataclass(frozen=True)
class NeverPrune:
    """Audit / forensic targets that the worker never touches."""

    path_relative: str
    rule_id: str


# ── Frozen rules ────────────────────────────────────────────────────────

ROTATION_RULES: tuple[RotationRule, ...] = (
    RotationRule(
        path_relative="chaos_logs.txt",
        rotate_at_bytes=50 * 1024 * 1024,
        keep_rotations=5,
        rule_id="chaos_logs",
    ),
    RotationRule(
        path_relative="execution_journal.jsonl",
        rotate_at_bytes=100 * 1024 * 1024,
        keep_rotations=10,
        rule_id="execution_journal",
    ),
    RotationRule(
        path_relative="backend/rl_status_snapshots.jsonl",
        rotate_at_bytes=50 * 1024 * 1024,
        keep_rotations=10,
        rule_id="rl_status_snapshots",
    ),
    RotationRule(
        path_relative="artifacts/runtime_health_transitions.jsonl",
        rotate_at_bytes=20 * 1024 * 1024,
        keep_rotations=10,
        rule_id="runtime_health_transitions",
    ),
    RotationRule(
        path_relative="artifacts/trading_gate_evidence.jsonl",
        rotate_at_bytes=20 * 1024 * 1024,
        keep_rotations=10,
        rule_id="trading_gate_evidence",
    ),
)


DIRECTORY_QUOTAS: tuple[DirectoryQuota, ...] = (
    DirectoryQuota(
        path_relative="artifacts",
        cap_bytes=4 * 1024 * 1024 * 1024,  # 4 GiB default
        keep_daily=7,
        keep_weekly=4,
        keep_monthly=3,
        rule_id="artifacts_quota",
    ),
)


NEVER_PRUNE: tuple[NeverPrune, ...] = (
    NeverPrune(path_relative="artifacts/ci/history.jsonl", rule_id="ci_history_audit"),
    NeverPrune(path_relative="artifacts/runtime_health.json", rule_id="runtime_health_current"),
    NeverPrune(path_relative="runtime_overrides.json", rule_id="runtime_overrides"),
    NeverPrune(path_relative="docs", rule_id="docs_dir"),
)


@dataclass(frozen=True)
class BoundedPass:
    """Per-invocation budget so a single retention pass always terminates."""

    max_files_to_delete: int = 200
    max_bytes_to_delete: int = 2 * 1024 * 1024 * 1024     # 2 GiB
    max_seconds: int = 60
    max_files_to_rotate: int = 20


PASS_BUDGET = BoundedPass()


def is_never_prune(path: Path, repo_root: Path) -> bool:
    """True iff `path` is within any NEVER_PRUNE entry."""
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    rel_str = str(rel).replace("\\", "/")
    for np in NEVER_PRUNE:
        target = np.path_relative
        if rel_str == target or rel_str.startswith(target + "/"):
            return True
    return False
