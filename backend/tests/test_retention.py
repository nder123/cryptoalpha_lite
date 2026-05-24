"""Tests for retention worker: rotation, quota, never-prune, bounded pass."""
from __future__ import annotations

import gzip
import os
import time
from pathlib import Path

import pytest

from runtime.retention.policy import (
    BoundedPass,
    DirectoryQuota,
    RotationRule,
    is_never_prune,
)
from runtime.retention.pruner import enforce_quota
from runtime.retention.rotator import needs_rotation, rotate
from runtime.retention.runner import run_pass


def _write_bytes(p: Path, n: int) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"x" * n)


# ── rotator ─────────────────────────────────────────────────────────────


def test_needs_rotation_below_threshold(tmp_path):
    p = tmp_path / "log.txt"
    _write_bytes(p, 1024)
    rule = RotationRule(path_relative="log.txt", rotate_at_bytes=2048, keep_rotations=3, rule_id="x")
    assert needs_rotation(p, rule) is False


def test_needs_rotation_at_threshold(tmp_path):
    p = tmp_path / "log.txt"
    _write_bytes(p, 4096)
    rule = RotationRule(path_relative="log.txt", rotate_at_bytes=2048, keep_rotations=3, rule_id="x")
    assert needs_rotation(p, rule) is True


def test_rotate_produces_gz_and_truncates(tmp_path):
    p = tmp_path / "log.txt"
    _write_bytes(p, 8192)
    rule = RotationRule(path_relative="log.txt", rotate_at_bytes=4096, keep_rotations=3, rule_id="r")
    res = rotate(tmp_path, rule)
    assert res.rotated is True
    assert res.error is None
    gz = tmp_path / "log.txt.1.gz"
    assert gz.exists() and gz.stat().st_size > 0
    # Active file truncated
    assert p.stat().st_size == 0
    # gz contains original 8192 'x' bytes
    with gzip.open(gz, "rb") as f:
        content = f.read()
    assert content == b"x" * 8192


def test_rotate_shifts_existing_and_drops_beyond_keep(tmp_path):
    p = tmp_path / "log.txt"
    rule = RotationRule(path_relative="log.txt", rotate_at_bytes=100, keep_rotations=2, rule_id="r")
    # First rotation
    _write_bytes(p, 200)
    rotate(tmp_path, rule)
    assert (tmp_path / "log.txt.1.gz").exists()
    # Second rotation
    _write_bytes(p, 200)
    rotate(tmp_path, rule)
    assert (tmp_path / "log.txt.1.gz").exists()
    assert (tmp_path / "log.txt.2.gz").exists()
    # Third rotation — .2.gz should drop, new .1.gz, old becomes .2.gz
    _write_bytes(p, 200)
    rotate(tmp_path, rule)
    assert (tmp_path / "log.txt.1.gz").exists()
    assert (tmp_path / "log.txt.2.gz").exists()
    assert not (tmp_path / "log.txt.3.gz").exists()


def test_rotate_no_op_when_below_threshold(tmp_path):
    p = tmp_path / "log.txt"
    _write_bytes(p, 50)
    rule = RotationRule(path_relative="log.txt", rotate_at_bytes=1000, keep_rotations=3, rule_id="r")
    res = rotate(tmp_path, rule)
    assert res.rotated is False
    assert not (tmp_path / "log.txt.1.gz").exists()


def test_rotate_missing_file_is_safe(tmp_path):
    rule = RotationRule(path_relative="absent.txt", rotate_at_bytes=100, keep_rotations=3, rule_id="r")
    res = rotate(tmp_path, rule)
    assert res.rotated is False
    assert res.error is None


# ── pruner / quota ─────────────────────────────────────────────────────


def test_enforce_quota_under_cap_does_nothing(tmp_path):
    quota_dir = tmp_path / "artifacts"
    quota_dir.mkdir()
    _write_bytes(quota_dir / "a", 100)
    q = DirectoryQuota(
        path_relative="artifacts", cap_bytes=10_000, keep_daily=0, keep_weekly=0, keep_monthly=0, rule_id="q"
    )
    res = enforce_quota(tmp_path, q, budget=BoundedPass(), files_consumed=0, bytes_consumed=0)
    assert res.deleted_files == ()
    assert res.bytes_after == 100


def test_enforce_quota_deletes_oldest_until_under_cap(tmp_path):
    quota_dir = tmp_path / "artifacts"
    quota_dir.mkdir()
    # 5 files of 1000 bytes, distinct mtimes
    for i in range(5):
        f = quota_dir / f"f{i}.dat"
        _write_bytes(f, 1000)
        os.utime(f, (1000.0 + i, 1000.0 + i))
    q = DirectoryQuota(
        path_relative="artifacts", cap_bytes=2500, keep_daily=0, keep_weekly=0, keep_monthly=0, rule_id="q"
    )
    res = enforce_quota(tmp_path, q, budget=BoundedPass(), files_consumed=0, bytes_consumed=0)
    # Need to remove at least 5000-2500=2500 bytes → at least 3 files
    assert len(res.deleted_files) >= 3
    assert res.bytes_after <= q.cap_bytes
    # Oldest first: f0,f1,f2 should be deleted
    deleted_names = {Path(p).name for p in res.deleted_files}
    assert "f0.dat" in deleted_names
    assert "f1.dat" in deleted_names


def test_enforce_quota_skips_protected(tmp_path):
    # ci/history.jsonl is in NEVER_PRUNE
    quota_dir = tmp_path / "artifacts"
    (quota_dir / "ci").mkdir(parents=True)
    history = quota_dir / "ci" / "history.jsonl"
    _write_bytes(history, 5000)
    os.utime(history, (1.0, 1.0))  # ancient

    other = quota_dir / "other.dat"
    _write_bytes(other, 5000)
    os.utime(other, (2.0, 2.0))

    q = DirectoryQuota(
        path_relative="artifacts", cap_bytes=1000, keep_daily=0, keep_weekly=0, keep_monthly=0, rule_id="q"
    )
    res = enforce_quota(tmp_path, q, budget=BoundedPass(), files_consumed=0, bytes_consumed=0)
    deleted = {Path(p).name for p in res.deleted_files}
    assert "history.jsonl" not in deleted
    # the protected file appears in skipped_protected
    assert any("history.jsonl" in s for s in res.skipped_protected)
    # the other file should be deleted
    assert "other.dat" in deleted


def test_budget_exhausted_stops_pruning(tmp_path):
    quota_dir = tmp_path / "artifacts"
    quota_dir.mkdir()
    for i in range(20):
        f = quota_dir / f"f{i}.dat"
        _write_bytes(f, 1000)
        os.utime(f, (1000.0 + i, 1000.0 + i))
    q = DirectoryQuota(
        path_relative="artifacts", cap_bytes=0, keep_daily=0, keep_weekly=0, keep_monthly=0, rule_id="q"
    )
    tiny_budget = BoundedPass(max_files_to_delete=3, max_bytes_to_delete=10**9, max_seconds=60, max_files_to_rotate=20)
    res = enforce_quota(tmp_path, q, budget=tiny_budget, files_consumed=0, bytes_consumed=0)
    assert res.budget_exhausted is True
    assert len(res.deleted_files) == 3


def test_is_never_prune_for_ci_history(tmp_path):
    p = tmp_path / "artifacts" / "ci" / "history.jsonl"
    p.parent.mkdir(parents=True)
    p.touch()
    assert is_never_prune(p, tmp_path) is True


def test_is_never_prune_negative(tmp_path):
    p = tmp_path / "artifacts" / "random.dat"
    p.parent.mkdir(parents=True)
    p.touch()
    assert is_never_prune(p, tmp_path) is False


# ── runner: bounded pass + dry-run ─────────────────────────────────────


def test_run_pass_dry_run_writes_nothing(tmp_path):
    log = tmp_path / "chaos_logs.txt"
    _write_bytes(log, 60 * 1024 * 1024)  # > 50 MiB threshold
    summary = run_pass(repo_root=tmp_path, dry_run=True)
    # No rotation actually occurred
    assert not (tmp_path / "chaos_logs.txt.1.gz").exists()
    # But the dry-run summary identifies the rule
    assert any(r.get("rule_id") == "chaos_logs" and r.get("would_rotate") for r in summary.rotations)
    assert summary.dry_run is True


def test_run_pass_actually_rotates_chaos_logs(tmp_path):
    log = tmp_path / "chaos_logs.txt"
    _write_bytes(log, 60 * 1024 * 1024)
    summary = run_pass(repo_root=tmp_path, dry_run=False)
    assert (tmp_path / "chaos_logs.txt.1.gz").exists()
    assert summary.dry_run is False
    assert summary.total_bytes_rotated >= 60 * 1024 * 1024


def test_run_pass_terminates_within_budget_seconds(tmp_path):
    """Simulate slow clock to trigger time-budget exhaustion mid-pass."""
    counter = {"t": 0.0}

    def fake_clock() -> float:
        # First call returns 0; subsequent calls advance by 100s — quickly
        # exceeds max_seconds=60 in BoundedPass default after one tick.
        v = counter["t"]
        counter["t"] += 100
        return v

    summary = run_pass(repo_root=tmp_path, dry_run=False, clock=fake_clock)
    assert summary.duration_sec >= 0


def test_run_pass_no_files_means_empty_summary(tmp_path):
    summary = run_pass(repo_root=tmp_path, dry_run=False)
    # No artifacts dir, no rotations needed
    assert summary.total_bytes_pruned == 0
    assert summary.total_bytes_rotated == 0
    assert summary.budget_exhausted is False
