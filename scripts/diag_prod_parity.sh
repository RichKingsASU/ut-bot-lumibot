#!/usr/bin/env bash
# Diagnostic Run: Production State & Migration Parity
# RUN THIS ON k2 (the edge box). It is READ-ONLY except for ONE labeled canary write (Phase 3).
# It does NOT apply migrations and does NOT apply the message_type constraint.
#
# Usage:
#   bash scripts/diag_prod_parity.sh                 # run diagnostic, print report, DO NOT send Telegram
#   bash scripts/diag_prod_parity.sh --send          # also send the report via Telegram to $TG_CHAT
#
# Connection: the script sources the edge .env and expects a Postgres URL to the cloud pooler in
#   $SUPABASE_DB_URL (preferred) or $DATABASE_URL. If neither is set, the SQL phases report NO_DATA.
set -uo pipefail

REPO="${REPO:-$HOME/ut-bot-lumibot}"
ENV_FILE="${ENV_FILE:-$REPO/.env}"
TG_CHAT="${TG_CHAT:-8641189809}"
EXPECTED_REF="wnigkahkamoizjpmpuxs"
EXPECTED_MTC="20260723100000_add_message_type_check.sql"
TICK_MOUNT="/mnt/tick-storage"
EXPECTED_UUID="267ED1667ED12F75"
TICK_TABLE="${TICK_TABLE:-trades}"     # override if your QuestDB tick table has another name
QDB_URL="${QDB_URL:-localhost:9000}"

SEND=0; [[ "${1:-}" == "--send" ]] && SEND=1

# ---- load edge env (for DB url + telegram token), without echoing secrets ----
[[ -f "$ENV_FILE" ]] && set -a && . "$ENV_FILE" 2>/dev/null && set +a
DB_URL="${SUPABASE_DB_URL:-${DATABASE_URL:-}}"

RPT=""
say(){ RPT+="$1"$'\n'; echo -e "$1"; }
raw(){ RPT+='```'$'\n'"$1"$'\n''```'$'\n'; echo "$1"; }   # capture raw output in report
sqlq(){ # $1 = SQL ; prints result or NO_DATA note
  if [[ -z "$DB_URL" ]]; then echo "NO_DATA: no SUPABASE_DB_URL/DATABASE_URL in $ENV_FILE"; return 2; fi
  psql "$DB_URL" -X -A -F$'\t' -v ON_ERROR_STOP=0 -c "$1" 2>&1
}

say "# Diagnostic Run: Production State & Migration Parity"
say "_host: $(hostname)  user: $(whoami)  date: $(date -Is)_"
say ""

# ================= PHASE 0 =================
say "## Phase 0 — Deployed State"
say "### 1. services active + start timestamps"
raw "$(systemctl status da-agents da-crypto-bot da-trading-bot --no-pager 2>&1)"
raw "$(systemctl show da-agents da-crypto-bot da-trading-bot -p Id -p ActiveState -p ExecMainStartTimestamp 2>&1)"
say "### 2. repo HEAD(main) vs running commit"
raw "$(cd "$REPO" && git log -1 --format='%H %ci' main 2>&1)"
say "_compare ExecMainStartTimestamp above against this commit date; if a service predates HEAD -> DEGRADED, restart before continuing._"
say "### 3. edge .env project ref (expect $EXPECTED_REF)"
if [[ -f "$ENV_FILE" ]]; then
  REF=$(grep -hoE '[a-z0-9]{20}\.supabase\.co' "$ENV_FILE" | head -1 | cut -d. -f1)
  raw "ref=${REF:-<none found>}   $( [[ "$REF" == "$EXPECTED_REF" ]] && echo PASS || echo 'FAIL/NO_DATA' )"
else raw "NO_DATA: $ENV_FILE not found"; fi

# ================= PHASE 1 =================
say "## Phase 1 — Migration Parity (Repo <-> Cloud)"
say "### 4. repo migrations"
raw "$(ls -1 "$REPO/supabase/migrations/" 2>&1)"
say "### 5. cloud schema_migrations"
raw "$(sqlq "SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version;")"
say "### 6. diff repo vs cloud (expect only $EXPECTED_MTC missing in cloud = PASS; anything else = FAIL)"
if [[ -n "$DB_URL" ]]; then
  REPO_V=$(ls -1 "$REPO/supabase/migrations/" | sed -E 's/_.*//' | sort -u)
  CLOUD_V=$(psql "$DB_URL" -X -A -t -c "SELECT version FROM supabase_migrations.schema_migrations;" 2>/dev/null | sort -u)
  raw "IN REPO, NOT IN CLOUD:"$'\n'"$(comm -23 <(echo "$REPO_V") <(echo "$CLOUD_V"))"
else raw "NO_DATA: no DB url"; fi
say "### 7. to_regclass('public.hitl_queue')"
raw "$(sqlq "SELECT to_regclass('public.hitl_queue');")"

# ================= PHASE 2 =================
say "## Phase 2 — PR #68 Blocking Unknowns"
say "### 8. telegram_outbox count"
raw "$(sqlq "SELECT count(*) FROM telegram_outbox;")"
say "### 9. message_type distribution"
raw "$(sqlq "SELECT message_type, count(*), max(created_at) FROM telegram_outbox GROUP BY 1 ORDER BY 2 DESC;")"
say "_any message_type outside the domain in $EXPECTED_MTC = FAIL (list offenders)._"
say "### 10. max(created_at) telegram_outbox"
raw "$(sqlq "SELECT max(created_at) FROM telegram_outbox;")"

# ================= PHASE 3 =================
say "## Phase 3 — Edge Write Path is Live"
say "### 11. component_heartbeat ages (STALE if > 2x cadence)"
raw "$(sqlq "SELECT component, max(updated_at), now() - max(updated_at) AS age FROM component_heartbeat GROUP BY 1 ORDER BY 3 DESC;")"
say "### 12. ground_truth.py"
raw "$(cd "$REPO" && python scripts/ground_truth.py 2>&1)"
say "### 13. CANARY write (component_heartbeat / component='verification_canary') then read-back"
if [[ -n "$DB_URL" ]]; then
  raw "$(psql "$DB_URL" -X -A -c \
    "INSERT INTO component_heartbeat (component, updated_at) VALUES ('verification_canary', now())
     ON CONFLICT (component) DO UPDATE SET updated_at = now();" 2>&1)"
  raw "read-back:"$'\n'"$(sqlq "SELECT component, updated_at, now()-updated_at AS age FROM component_heartbeat WHERE component='verification_canary';")"
else raw "NO_DATA: no DB url — canary skipped"; fi

# ================= PHASE 4 =================
say "## Phase 4 — Tick Storage on the Edge"
say "### 14. findmnt $TICK_MOUNT (expect UUID $EXPECTED_UUID)"
FM="$(findmnt "$TICK_MOUNT" -o TARGET,SOURCE,UUID,FSTYPE 2>&1)"
raw "$FM"
NODE="$(findmnt -n "$TICK_MOUNT" -o SOURCE 2>/dev/null)"
say "### 15. smartctl -H ${NODE:-<node>}"
if command -v smartctl >/dev/null && [[ -n "$NODE" ]]; then raw "$(sudo smartctl -H "$NODE" 2>&1; sudo smartctl -A "$NODE" 2>&1 | grep -iE 'temperature')"
else raw "NO_DATA: smartctl missing or no device node"; fi
say "### 16. df -h $TICK_MOUNT"
raw "$(df -h "$TICK_MOUNT" 2>&1)"
say "### 17. QuestDB freshness (stale during market hours = FAIL)"
raw "$(curl -sG "$QDB_URL/exec" --data-urlencode "query=SELECT symbol, max(timestamp) FROM $TICK_TABLE GROUP BY symbol" 2>&1)"
say "### 18. QuestDB / Qdrant silent-degradation log scan (24h)"
raw "questdb: $(docker logs --since 24h questdb 2>&1 | grep -iE 'errno=5|No such file' | tail -20 || echo none)"
raw "qdrant:  $(docker logs --since 24h qdrant 2>&1 | grep -iE 'errno=5|No such file' | tail -20 || echo none)"

# ================= PHASE 5 =================
say "## Phase 5 — Credential Surface (read-only inventory)"
say "### 19. Supabase key formats per service (first 8 chars only)"
if [[ -f "$ENV_FILE" ]]; then
  raw "$(grep -hE 'SUPABASE.*KEY|ANON|SERVICE_ROLE' "$ENV_FILE" | sed -E 's/^([^=]+)=(.{0,8}).*/\1=\2.../' )"
  raw "legacy eyJ JWT prefixes present? -> $(grep -qE '=eyJ' "$ENV_FILE" && echo YES || echo no)"
else raw "NO_DATA: $ENV_FILE not found"; fi
say "### 20. TELEGRAM_BOT_TOKEN location (.env vs Doppler)"
IN_ENV=$(grep -qE '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" 2>/dev/null && echo yes || echo no)
IN_DOP=$(command -v doppler >/dev/null && doppler secrets 2>/dev/null | grep -q TELEGRAM_BOT_TOKEN && echo yes || echo no)
raw "in .env=$IN_ENV   in doppler=$IN_DOP"

say ""
say "## END OF REPORT — apply PASS/FAIL/NO_DATA/STALE per line from the raw output above."

# ---- optional Telegram send (outward-facing; opt-in only) ----
if [[ "$SEND" -eq 1 ]]; then
  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TG_CHAT}" \
      --data-urlencode "text=${RPT}" \
      -d parse_mode=Markdown >/dev/null && echo "[sent to $TG_CHAT]" || echo "[telegram send FAILED]"
  else
    echo "[--send requested but TELEGRAM_BOT_TOKEN not set; not sent]"
  fi
else
  echo "[report not sent; re-run with --send to deliver to Telegram $TG_CHAT]"
fi
