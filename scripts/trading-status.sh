#!/bin/bash
set -euo pipefail
runtime=${DA_RUNTIME_DIR:-/run/disrupting-alpha}
state=${DA_STATE_DIR:-/var/lib/disrupting-alpha}
if test -e "$state/trading-disabled" || test -e "$runtime/trading-disabled"; then
  echo "STATUS: ENTRY DISABLED"
  test -r "$state/trading-disabled" && cat "$state/trading-disabled"
  test -e "$state/trading-enable-requested" && echo "ENABLE: REQUESTED (not acknowledged)"
  exit 1
fi
echo "STATUS: ENABLED"; exit 0
