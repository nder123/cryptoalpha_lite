#!/bin/bash
set -euo pipefail

echo "=== RL ops summary ($(date -Is)) ==="
echo

echo "-- /api/rl/status (compact)"
if status_json=$(curl -fsS --max-time 3 http://127.0.0.1:8000/api/rl/status); then
  printf '%s' "$status_json" | python -c 'import json,sys; j=json.load(sys.stdin); p=j.get("policy") or {}; print(f"active_policy_version={j.get('"'"'active_policy_version'"'"')}"); print(f"latest_policy_version={p.get('"'"'version'"'"')}")'
else
  echo "ERROR: failed to fetch /api/rl/status"
fi

echo
echo "-- /api/rl/policy/loaded"
curl -fsS --max-time 3 http://127.0.0.1:8000/api/rl/policy/loaded || echo "ERROR: failed to fetch /api/rl/policy/loaded"

echo
echo "-- recommender alerts (tag=cryptoalpha-rl-alert, priority=alert)"
journalctl --user -t cryptoalpha-rl-alert -p alert -n 20 --no-pager --output=cat || true

echo
echo "-- recommender digest (cryptoalpha-recommender-events.service)"
journalctl --user -u cryptoalpha-recommender-events.service -n 60 --no-pager --output=cat || true

echo
echo "-- timers"
systemctl --user list-timers --all --no-pager | grep -E "cryptoalpha-recommender-(events|alerts)" || echo "(timers not found)"

echo
echo "=== end ==="
