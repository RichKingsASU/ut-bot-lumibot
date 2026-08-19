#!/bin/bash
set -euo pipefail
runtime=${DA_RUNTIME_DIR:-/run/disrupting-alpha}
state=${DA_STATE_DIR:-/var/lib/disrupting-alpha}
umask 027
install -d -m 0750 "$runtime" "$state"
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"state":"KILL_REQUESTED","reason":"EMERGENCY_KILL","requested_at":"%s","attempts":0,"last_error":null}\n' "$now" > "$state/trading-disabled.tmp"
chmod 0640 "$state/trading-disabled.tmp"
mv "$state/trading-disabled.tmp" "$state/trading-disabled"
: > "$runtime/trading-disabled"; chmod 0640 "$runtime/trading-disabled"
printf 'KILL_REQUESTED persisted; entries are disabled. Flatness is not yet confirmed.\n'
