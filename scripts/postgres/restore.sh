#!/usr/bin/env bash
set -euo pipefail
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required}"
: "${1:?usage: restore.sh BACKUP.dump}"
[[ "${CONFIRM_DESTRUCTIVE_RESTORE:-}" == "RESTORE" ]] || { echo "Set CONFIRM_DESTRUCTIVE_RESTORE=RESTORE" >&2; exit 2; }
sha256sum --check "$1.sha256"
pg_restore --dbname="$RESTORE_DATABASE_URL" --clean --if-exists --no-owner --no-acl --exit-on-error "$1"
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'SELECT COUNT(*) AS audit_events FROM operations_auditevent;' -c 'SELECT COUNT(*) AS orders FROM trading_order;'
