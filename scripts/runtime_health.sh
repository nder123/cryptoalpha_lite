#!/usr/bin/env bash
# Runtime health probe — authoritative per docs/runtime_bootstrap_contract_v1.md §5
#
# Exit codes:
#   0  HEALTHY    every probe passed
#   1  CRITICAL   at least one critical probe failed
#   2  DEGRADED   only non-critical probes failed
#
# Usage: scripts/runtime_health.sh [-v]

set -euo pipefail

VERBOSE=0
if [[ "${1:-}" == "-v" || "${1:-}" == "--verbose" ]]; then
  VERBOSE=1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${RUNTIME_DATA_DIR:-$HOME/.local/state/cryptoalpha}"
ENV_FILE="$HOME/.config/cryptoalpha/env"
SNAPSHOTS_FILE="$REPO_ROOT/backend/rl_status_snapshots.jsonl"

CRITICAL_FAILS=0
DEGRADED_FAILS=0

log() {
  echo "[runtime_health] $*" >&2
}

vlog() {
  [[ "$VERBOSE" -eq 1 ]] && log "$*" || true
}

probe_critical() {
  local name="$1"; shift
  if "$@"; then
    vlog "OK  (critical) $name"
  else
    log "FAIL (critical) $name"
    CRITICAL_FAILS=$((CRITICAL_FAILS + 1))
  fi
}

probe_soft() {
  local name="$1"; shift
  if "$@"; then
    vlog "OK  (soft)     $name"
  else
    log "FAIL (soft)     $name"
    DEGRADED_FAILS=$((DEGRADED_FAILS + 1))
  fi
}

# 1. backend service active
chk_backend_active() {
  systemctl --user is-active --quiet cryptoalpha-backend.service
}

# 2. /api/health 2xx within 5s
chk_api_health() {
  curl -fsS --max-time 5 http://127.0.0.1:8000/api/health >/dev/null
}

# 3. snapshots service active
chk_snapshots_active() {
  systemctl --user is-active --quiet cryptoalpha-snapshots.service
}

# 4. recommender service active
chk_recommender_active() {
  systemctl --user is-active --quiet cryptoalpha-recommender.service
}

# 5. last snapshot line <= 5 min old
chk_snapshots_fresh() {
  [[ -f "$SNAPSHOTS_FILE" ]] || return 1
  local mtime now age
  mtime=$(stat -c %Y "$SNAPSHOTS_FILE" 2>/dev/null || echo 0)
  now=$(date +%s)
  age=$((now - mtime))
  [[ "$age" -le 300 ]]
}

# 6. env file exists and mode <= 0600
chk_env_file_secure() {
  [[ -f "$ENV_FILE" ]] || return 1
  local mode
  mode=$(stat -c %a "$ENV_FILE" 2>/dev/null || echo 777)
  # accept 600, 400, etc; reject group/world bits
  [[ "$mode" =~ ^[0-7]00$ ]]
}

# 7. disk free >= 200 MiB on repo and state dir
chk_disk_free() {
  local min_kb=204800  # 200 MiB
  local repo_free state_free
  repo_free=$(df -P "$REPO_ROOT" | awk 'NR==2 {print $4}')
  mkdir -p "$STATE_DIR" 2>/dev/null || true
  state_free=$(df -P "$STATE_DIR" | awk 'NR==2 {print $4}')
  [[ "$repo_free" -ge "$min_kb" ]] && [[ "$state_free" -ge "$min_kb" ]]
}

probe_critical "backend service active"             chk_backend_active
probe_critical "GET /api/health"                    chk_api_health
probe_soft     "snapshots service active"           chk_snapshots_active
probe_soft     "recommender service active"         chk_recommender_active
probe_soft     "snapshots file fresh (<=5 min)"     chk_snapshots_fresh
probe_critical "env file present and mode <= 0600"  chk_env_file_secure
probe_critical "disk free >= 200 MiB (repo,state)"  chk_disk_free

if [[ "$CRITICAL_FAILS" -gt 0 ]]; then
  log "STATUS: CRITICAL (critical_fails=$CRITICAL_FAILS degraded_fails=$DEGRADED_FAILS)"
  exit 1
fi
if [[ "$DEGRADED_FAILS" -gt 0 ]]; then
  log "STATUS: DEGRADED (degraded_fails=$DEGRADED_FAILS)"
  exit 2
fi
log "STATUS: HEALTHY"
exit 0
