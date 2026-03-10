#!/bin/bash
set -euo pipefail

echo "=== RL ops summary ($(date -Is)) ==="
echo

echo "-- /api/rl/status (compact)"
VERDICT="OK"
DETAILS=()
ACTIVE_POLICY_VERSION=""
LATEST_POLICY_VERSION=""
if status_json=$(curl -fsS --max-time 3 http://127.0.0.1:8000/api/rl/status); then
  ACTIVE_POLICY_VERSION=$(printf '%s' "$status_json" | python -c 'import json,sys; j=json.load(sys.stdin); v=j.get("active_policy_version") or ""; print(v)')
  LATEST_POLICY_VERSION=$(printf '%s' "$status_json" | python -c 'import json,sys; j=json.load(sys.stdin); p=j.get("policy") or {}; v=p.get("version") or ""; print(v)')
else
  VERDICT="ATTENTION"
  DETAILS+=("status_fetch_failed")
fi

if [ -z "$ACTIVE_POLICY_VERSION" ] || [ -z "$LATEST_POLICY_VERSION" ]; then
  VERDICT="ATTENTION"
  DETAILS+=("missing_versions")
elif [ "$ACTIVE_POLICY_VERSION" != "$LATEST_POLICY_VERSION" ]; then
  VERDICT="ATTENTION"
  DETAILS+=("latest!=active")
fi

echo "active_policy_version=$ACTIVE_POLICY_VERSION"
echo "latest_policy_version=$LATEST_POLICY_VERSION"

echo
echo "-- /api/rl/policy/loaded"
LOADED_POLICY_VERSION=""
LOADED_ACTIVE_VERSION=""
LOADED_REDIS_KEY=""
loaded_json=""
if loaded_json=$(curl -fsS --max-time 3 http://127.0.0.1:8000/api/rl/policy/loaded); then
  LOADED_POLICY_VERSION=$(printf '%s' "$loaded_json" | python -c 'import json,sys; j=json.load(sys.stdin); print(j.get("policy_version") or "")')
  LOADED_ACTIVE_VERSION=$(printf '%s' "$loaded_json" | python -c 'import json,sys; j=json.load(sys.stdin); print(j.get("active_policy_version") or "")')
  LOADED_REDIS_KEY=$(printf '%s' "$loaded_json" | python -c 'import json,sys; j=json.load(sys.stdin); print(j.get("redis_key") or "")')
  printf '%s' "$loaded_json" | python -m json.tool
else
  VERDICT="ATTENTION"
  DETAILS+=("policy_loaded_fetch_failed")
  echo "ERROR: failed to fetch /api/rl/policy/loaded"
fi

if [ -n "$LOADED_ACTIVE_VERSION" ] && [ -n "$LOADED_POLICY_VERSION" ] && [ "$LOADED_POLICY_VERSION" != "$LOADED_ACTIVE_VERSION" ]; then
  VERDICT="ATTENTION"
  DETAILS+=("loaded_policy_version!=active")
fi

if [ -n "$ACTIVE_POLICY_VERSION" ]; then
  expected_key="rl_policy:by_version:$ACTIVE_POLICY_VERSION"
  if [ -n "$LOADED_REDIS_KEY" ] && [ "$LOADED_REDIS_KEY" != "$expected_key" ]; then
    VERDICT="ATTENTION"
    DETAILS+=("loaded_redis_key!=by_version")
  fi
  if [ -n "$LOADED_ACTIVE_VERSION" ] && [ "$LOADED_ACTIVE_VERSION" != "$ACTIVE_POLICY_VERSION" ]; then
    VERDICT="ATTENTION"
    DETAILS+=("loaded_active!=status_active")
  fi
fi

echo
if [ ${#DETAILS[@]} -gt 0 ]; then
  echo "verdict=$VERDICT ($(IFS=,; echo "${DETAILS[*]}") )" | sed -E 's/ \)/)/'
else
  echo "verdict=$VERDICT"
fi

echo
echo "-- recommender alerts (tag=cryptoalpha-rl-alert, priority=alert)"
journalctl --user -t cryptoalpha-rl-alert -p alert -n 20 --no-pager --output=cat || true

echo
echo "-- recommender digest (cryptoalpha-recommender-events.service)"
digest_lines=$(journalctl --user -u cryptoalpha-recommender-events.service -n 400 --no-pager --output=cat \
  | grep -E "PROMOTE_RECOMMENDED|NOT_RECOMMENDED|ROLLBACK_RECOMMENDED|no recommender events in window" \
  | sed -E 's/\\n.*$//' \
  | awk '!seen[$0]++' \
  | tail -n 12 \
  || true)
if [ -n "$digest_lines" ]; then
  echo "$digest_lines"
else
  echo "(no digest lines)"
fi

echo
echo "-- timers"
systemctl --user list-timers --all --no-pager | grep -E "cryptoalpha-recommender-(events|alerts)" || echo "(timers not found)"

echo
echo "=== end ==="
