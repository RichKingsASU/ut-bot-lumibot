#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
backup_dir="${BACKUP_DIR:-./backups}"; mkdir -p "$backup_dir"; umask 077
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"; output="$backup_dir/lumibot-$timestamp.dump"
pg_dump --dbname="$DATABASE_URL" --format=custom --compress=9 --no-owner --no-acl --file="$output"
sha256sum "$output" > "$output.sha256"
echo "$output"
