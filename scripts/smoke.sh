#!/usr/bin/env bash
# Non-destructive smoke test of the running stack (no attacks, no external traffic).
set -u; B=http://127.0.0.1:8077
echo "health:        $(curl -s -m5 -o /dev/null -w '%{http_code}' $B/api/health)"
echo "public reject: $(curl -s -m6 -X POST $B/api/network/targets/select -H 'content-type: application/json' --data-binary '{"ip":"8.8.8.8"}' -o /dev/null -w '%{http_code}') (expect 400)"
echo "telemetry src: $(curl -s -m5 $B/api/health | python3 -c 'import sys,json;print(json.load(sys.stdin).get("telemetry_source"))')"
