#!/usr/bin/env bash
# CryptoAlpha bootstrap — runtime first-start contract
# Authoritative spec: docs/runtime_bootstrap_contract_v1.md §1
#
# Exit codes:
#   0  bootstrap complete, runtime HEALTHY
#   1  precondition failed (env / deps)
#   2  services started but unhealthy

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="$HOME/.config/cryptoalpha"
ENV_FILE="$ENV_DIR/env"
TEMPLATE="$REPO_ROOT/.env.template"
STATE_DIR="${RUNTIME_DATA_DIR:-$HOME/.local/state/cryptoalpha}"
CACHE_DIR="$HOME/.cache/cryptoalpha"
SYSTEMD_DIR="$HOME/.config/systemd/user"
UNITS_SRC="$REPO_ROOT/ops/systemd-user"

REQUIRED_VARS=(OPERATOR_API_KEY RUNTIME_MODE)
LONG_RUNNING=(cryptoalpha-backend.service cryptoalpha-snapshots.service cryptoalpha-recommender.service)
TIMERS=(cryptoalpha-duty-check.timer cryptoalpha-recommender-events.timer cryptoalpha-recommender-alerts.timer cryptoalpha-rl-ops-summary.timer cryptoalpha-retention.timer)

log() { echo "[bootstrap] $*" >&2; }
journ() {
  if command -v systemd-cat >/dev/null 2>&1; then
    echo "$*" | systemd-cat -t cryptoalpha-bootstrap
  fi
}

step() {
  log "── step: $*"
  journ "step: $*"
}

# ── step 1: env contract ───────────────────────────────────────────────
step "1. env contract"
mkdir -p "$ENV_DIR"
chmod 0700 "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ ! -f "$TEMPLATE" ]]; then
    log "FATAL: neither $ENV_FILE nor $TEMPLATE exists"
    exit 1
  fi
  log "creating $ENV_FILE from .env.template (REQUIRED values are blank)"
  install -m 0600 "$TEMPLATE" "$ENV_FILE"
  log "edit $ENV_FILE to fill in required values, then re-run bootstrap"
  exit 1
fi
chmod 0600 "$ENV_FILE"

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

missing=()
for v in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    missing+=("$v")
  fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
  log "FATAL: required env vars unset: ${missing[*]}"
  exit 1
fi

# ── step 2: directories ────────────────────────────────────────────────
step "2. directories"
mkdir -p "$STATE_DIR" "$CACHE_DIR" "$SYSTEMD_DIR"
chmod 0700 "$STATE_DIR"
mkdir -p "$REPO_ROOT/artifacts" "$REPO_ROOT/snapshots"

# warn on oversized chaos_logs
if [[ -f "$REPO_ROOT/chaos_logs.txt" ]]; then
  size_mb=$(du -m "$REPO_ROOT/chaos_logs.txt" | awk '{print $1}')
  if [[ "$size_mb" -gt 100 ]]; then
    log "WARN: chaos_logs.txt is ${size_mb} MiB (Phase 1D retention not yet active)"
  fi
fi

# ── step 3: python deps ────────────────────────────────────────────────
step "3. python deps (poetry install in backend/)"
if ! command -v poetry >/dev/null 2>&1 && [[ ! -x "$HOME/.local/bin/poetry" ]]; then
  log "FATAL: poetry not found in PATH or ~/.local/bin"
  exit 1
fi
POETRY_BIN="${POETRY_BIN:-$(command -v poetry || echo $HOME/.local/bin/poetry)}"
( cd "$REPO_ROOT/backend" && "$POETRY_BIN" install --no-interaction --no-root ) || {
  log "FATAL: poetry install failed"
  exit 1
}

# ── step 4: database / state ───────────────────────────────────────────
step "4. database / state — deferred to backend on first start"

# ── step 5: systemd unit symlinks ──────────────────────────────────────
step "5. systemd unit symlinks"
shopt -s nullglob
for src in "$UNITS_SRC"/*.service "$UNITS_SRC"/*.timer; do
  base=$(basename "$src")
  dst="$SYSTEMD_DIR/$base"
  if [[ -L "$dst" || -f "$dst" ]]; then
    rm -f "$dst"
  fi
  ln -s "$src" "$dst"
done
shopt -u nullglob

# ── step 6: supervisor reload ──────────────────────────────────────────
step "6. systemctl --user daemon-reload"
systemctl --user daemon-reload

# ── step 7: service start ──────────────────────────────────────────────
step "7. start long-running services"
for unit in "${LONG_RUNNING[@]}"; do
  log "  enable --now $unit"
  systemctl --user enable --now "$unit"
done

# ── step 8: health validation (up to 120s) ─────────────────────────────
step "8. health validation"
deadline=$(( $(date +%s) + 120 ))
status=2
while [[ "$(date +%s)" -lt "$deadline" ]]; do
  set +e
  "$REPO_ROOT/scripts/runtime_health.sh"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then break; fi
  sleep 3
done
if [[ "$status" -ne 0 ]]; then
  log "ERROR: runtime did not become HEALTHY within 120s (status=$status)"
  journ "FAILED status=$status"
  exit 2
fi

# ── step 9: timer enablement ───────────────────────────────────────────
step "9. enable timers"
for t in "${TIMERS[@]}"; do
  log "  enable --now $t"
  systemctl --user enable --now "$t"
done

# ── step 10: ready ─────────────────────────────────────────────────────
step "10. ready"
journ "READY"
log "bootstrap complete, runtime HEALTHY"
exit 0
