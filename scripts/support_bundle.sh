#!/usr/bin/env bash
# Build an operator support bundle.
# Authoritative spec: docs/runtime_bootstrap_contract_v1.md §9 (bundle contents)
#
# Output: ~/.local/state/cryptoalpha/support_bundle_<YYYYMMDD-HHMMSS>.tar.zst
#
# Exit codes:
#   0  bundle written
#   1  I/O / permission failure
#   2  bundle truncated due to caps

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${RUNTIME_DATA_DIR:-$HOME/.local/state/cryptoalpha}"
TS="$(date +%Y%m%d-%H%M%S)"
WORKDIR="$(mktemp -d)"
BUNDLE_DIR="$WORKDIR/support_bundle_$TS"
OUT="$STATE_DIR/support_bundle_${TS}.tar.zst"
MAX_BUNDLE_MB=100
TRUNCATED=0

trap 'rm -rf "$WORKDIR"' EXIT

log() { echo "[support_bundle] $*" >&2; }
journ() {
  command -v systemd-cat >/dev/null 2>&1 && echo "$*" | systemd-cat -t cryptoalpha-support || true
}

mkdir -p "$STATE_DIR" "$BUNDLE_DIR"

# ── journald (last 7 days) ─────────────────────────────────────────────
log "collecting journald (cryptoalpha-* last 7 days)"
journalctl --user --since "7 days ago" --no-pager \
  -u 'cryptoalpha-*' \
  > "$BUNDLE_DIR/journal_7d.log" 2>/dev/null || true

# ── unit states ────────────────────────────────────────────────────────
log "collecting unit states"
systemctl --user list-units 'cryptoalpha*' --all --no-pager \
  > "$BUNDLE_DIR/unit_states.txt" 2>/dev/null || true
systemctl --user list-timers 'cryptoalpha*' --all --no-pager \
  > "$BUNDLE_DIR/timers.txt" 2>/dev/null || true

# ── runtime overrides ──────────────────────────────────────────────────
if [[ -f "$REPO_ROOT/runtime_overrides.json" ]]; then
  cp "$REPO_ROOT/runtime_overrides.json" "$BUNDLE_DIR/runtime_overrides.json"
fi

# ── ledger & snapshots tails ───────────────────────────────────────────
if [[ -f "$REPO_ROOT/execution_journal.jsonl" ]]; then
  tail -n 1000 "$REPO_ROOT/execution_journal.jsonl" > "$BUNDLE_DIR/execution_journal_tail.jsonl"
fi
if [[ -f "$REPO_ROOT/backend/rl_status_snapshots.jsonl" ]]; then
  tail -n 1000 "$REPO_ROOT/backend/rl_status_snapshots.jsonl" > "$BUNDLE_DIR/rl_status_snapshots_tail.jsonl"
fi

# ── health snapshot ────────────────────────────────────────────────────
log "running runtime_health.sh -v"
set +e
"$REPO_ROOT/scripts/runtime_health.sh" -v > "$BUNDLE_DIR/runtime_health.txt" 2>&1
echo "exit_code=$?" >> "$BUNDLE_DIR/runtime_health.txt"
set -e

# ── disk ───────────────────────────────────────────────────────────────
{
  df -h "$REPO_ROOT" "$STATE_DIR" 2>/dev/null
  echo "----"
  du -sh "$REPO_ROOT/artifacts" "$REPO_ROOT/snapshots" "$STATE_DIR" 2>/dev/null
} > "$BUNDLE_DIR/disk.txt" || true

# ── deliberate exclusions ──────────────────────────────────────────────
# - ~/.config/cryptoalpha/env  (secrets)
# - chaos_logs.txt             (oversized, retention not implemented)
echo "secrets / chaos_logs.txt deliberately excluded per contract §9" \
  > "$BUNDLE_DIR/EXCLUSIONS.txt"

# ── pack ───────────────────────────────────────────────────────────────
log "packing bundle"
if ! command -v zstd >/dev/null 2>&1; then
  log "FATAL: zstd not installed"
  exit 1
fi
( cd "$WORKDIR" && tar --zstd -cf "$OUT" "support_bundle_$TS" ) || {
  log "FATAL: tar/zstd failed"
  exit 1
}

# ── size cap ───────────────────────────────────────────────────────────
size_mb=$(du -m "$OUT" | awk '{print $1}')
if [[ "$size_mb" -gt "$MAX_BUNDLE_MB" ]]; then
  log "WARN: bundle ${size_mb} MiB exceeds soft cap ${MAX_BUNDLE_MB} MiB"
  TRUNCATED=1
fi

log "wrote $OUT (${size_mb} MiB)"
journ "wrote $OUT size_mb=$size_mb truncated=$TRUNCATED"
echo "$OUT"

[[ "$TRUNCATED" -eq 1 ]] && exit 2 || exit 0
