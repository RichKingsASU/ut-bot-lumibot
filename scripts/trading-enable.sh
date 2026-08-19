#!/bin/bash
set -euo pipefail
state=${DA_STATE_DIR:-/var/lib/disrupting-alpha}
test "$(id -u)" -eq 0 || test "$(id -un)" = "${DA_SERVICE_USER:-k2}" || {
  echo "Denied: run as root or DA_SERVICE_USER" >&2; exit 77;
}
test -r "$state/trading-disabled" || { echo "Trading is already enabled"; exit 0; }
python3 - "$state/trading-disabled" <<'PY'
import json,sys
try: state=json.load(open(sys.argv[1]))
except Exception as exc: raise SystemExit(f"Denied: invalid kill state: {exc}")
if state.get("state") != "KILLED_FLAT": raise SystemExit("Denied: broker-flat state unresolved")
PY
umask 027
: > "$state/trading-enable-requested"; chmod 0640 "$state/trading-enable-requested"
echo "Enable requested. The canonical executor must reconcile broker state and acknowledge it."
