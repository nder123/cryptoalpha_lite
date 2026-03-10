#!/bin/bash
set -euo pipefail

echo "=== RL ops summary ($(date -Is)) ==="
echo

echo "-- /api/rl/status (compact)"
if status_json=$(curl -fsS --max-time 3 http://127.0.0.1:8000/api/rl/status); then
  printf '%s' "$status_json" | python -c 'import json,sys; j=json.load(sys.stdin); p=j.get("policy") or {}; active=j.get("active_policy_version"); latest=p.get("version"); verdict="OK"; details="";  \
verdict,details=("ATTENTION","missing versions") if (not active or not latest) else (verdict,details);  \
verdict,details=("ATTENTION","latest!=active") if (active and latest and active!=latest) else (verdict,details);  \
suffix=(" ("+details+")") if details else ""; print("verdict=%s%s" % (verdict, suffix)); print("active_policy_version=%s" % (active,)); print("latest_policy_version=%s" % (latest,))'
else
  echo "ERROR: failed to fetch /api/rl/status"
fi

echo
echo "-- /api/rl/policy/loaded"
if loaded_json=$(curl -fsS --max-time 3 http://127.0.0.1:8000/api/rl/policy/loaded); then
  printf '%s' "$loaded_json" | python -m json.tool
else
  echo "ERROR: failed to fetch /api/rl/policy/loaded"
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
