#!/usr/bin/env bash
# Start the long-running runtime services in order.
# Authoritative spec: docs/runtime_bootstrap_contract_v1.md §9
#
# Exit codes:
#   0  all long-running units active
#   1  systemd command failed
#   2  unit started but unhealthy

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LONG_RUNNING=(cryptoalpha-backend.service cryptoalpha-snapshots.service cryptoalpha-recommender.service)

log() { echo "[start_runtime] $*" >&2; }
journ() {
  if command -v systemd-cat >/dev/null 2>&1; then
    echo "$*" | systemd-cat -t cryptoalpha-start
  fi
}

for unit in "${LONG_RUNNING[@]}"; do
  log "starting $unit"
  if ! systemctl --user start "$unit"; then
    log "FATAL: failed to start $unit"
    journ "FAILED unit=$unit"
    exit 1
  fi
done

# verify active
for unit in "${LONG_RUNNING[@]}"; do
  if ! systemctl --user is-active --quiet "$unit"; then
    log "ERROR: $unit not active after start"
    exit 1
  fi
done

# health check (single pass; bootstrap.sh has retry loop)
log "validating health"
set +e
"$REPO_ROOT/scripts/runtime_health.sh"
status=$?
set -e

case "$status" in
  0) log "HEALTHY"; journ "HEALTHY"; exit 0 ;;
  2) log "DEGRADED (non-critical probes failed)"; journ "DEGRADED"; exit 2 ;;
  *) log "UNHEALTHY (status=$status)"; journ "UNHEALTHY status=$status"; exit 2 ;;
esac
