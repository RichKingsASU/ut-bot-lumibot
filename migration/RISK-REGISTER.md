# Migration risk register

No secret values appear in this file. Key IDs and service-account emails are
identifiers, not credentials.

## R-01 — Long-lived service-account key (OPEN, HIGH)

    Service account   gcp-replicator@disruptingalpha.iam.gserviceaccount.com
    Key ID            1d1425a2351f70ca92a89eaadcbe61b48ffe1662
    Created           Cloud Shell, 2026-08-08
    Scope             roles/pubsub.publisher, roles/bigquery.dataEditor
    Purpose           Temporary bare-metal POC auth for da-gcp-replicator
    Replacement       Workload Identity Federation
    Stored at         /home/k2/.config/disruptingalpha/gcp-replicator.json (0600)

A long-lived key on a bare-metal host is the weakest link in this design. It
does not expire, and possession of the file is sufficient to publish to Pub/Sub
and write to BigQuery in `disruptingalpha`.

**Deleting the local JSON is NOT revocation.** The key stays valid in GCP until
deleted there:

    gcloud iam service-accounts keys delete 1d1425a2351f70ca92a89eaadcbe61b48ffe1662 \
      --iam-account=gcp-replicator@disruptingalpha.iam.gserviceaccount.com

Cleanup required once WIF is verified.

Blocker for WIF: `_load_service_account` uses
`service_account.Credentials.from_service_account_file`, which only accepts
`"type": "service_account"`. A WIF config is `"type": "external_account"` and is
rejected. Switching to `google.auth.default()` handles both. Verified by test:
`from_service_account_file` on a WIF config raises
`MalformedError: missing fields client_email, token_uri`, while
`google.auth.default()` loads it.

## R-02 — Supabase database password exposed in a chat transcript (DEFERRED, HIGH)

    Accepted by  : repository owner, 2026-08-12
    Review date  : 2026-11-12
    Status       : risk accepted, not mitigated

The current `SUPABASE_DSN` password was transmitted through an assistant
conversation, which is a durable log outside this host. It grants full
read/write access to the production database.

**Deferred by explicit decision on 2026-08-12, to be revisited 2026-11-12.**
Recording it as accepted rather than closed: the exposure is unchanged and does
not decay with time. Anyone with access to that transcript can reach the
production database until the password is rotated.

Rotation itself is cheap and was verified as low-risk. Only `da-gcp-replicator`
holds the DSN -- confirmed by reading `/proc/<pid>/environ` on all five running
services; the four trading services carry only `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY` (REST) and never see the database password. No
systemd unit references a DSN. Cost of rotating is a ~10s telemetry gap:

    ALTER USER postgres WITH PASSWORD '<new 32-char alphanumeric>';
    # update SUPABASE_DSN in .env
    sudo systemctl restart da-gcp-replicator

Rotate sooner than the review date if any of these change: the transcript is
shared or exported, the replicator is restarted for another reason anyway
(free window), or the account moves to a shared/team context.

An earlier password was also transmitted. If that one was the Supabase
*account* password rather than the database password, it should be rotated
regardless of this deferral -- account access controls the project, its data,
and billing, and is not covered by the reasoning above.

## R-03 — pg_partman partitions stop silently after migration (OPEN, HIGH)

`ohlcv_bars` is partitioned with monthly partitions through `p20261001`,
created by pg_partman 5.3.1 and maintained by the hourly `partman-maintenance`
cron job.

A dump/restore that copies tables but not `part_config`, `part_config_sub`,
`template_public_ohlcv_bars` and the cron schedule appears to succeed. Inserts
keep working until the last pre-created partition is passed, then fail --
months after cutover, when the cause is no longer obvious.

Mitigation: migrate partman config explicitly; enable pg_cron on Cloud SQL and
re-create the maintenance schedule; verify a future partition is created before
declaring cutover complete.

## R-04 — pg_cron jobs dropped in migration (OPEN, HIGH)

    [2] 0 * * * *      partman-maintenance      partition maintenance
    [3] 30 11 * * 1-5  refresh-open-interest     weekday market hours
    [4] * * * * *      hitl_queue_expire_job     every 60s

`hitl_queue_expire_job` operates the human-in-the-loop gate (`HITL_ENABLED` is
set on k2). If it stops, HITL entries stop expiring -- a trading-safety
behaviour change, not a cosmetic one.

None are visible through PostgREST. A REST-only audit would have migrated the
data and silently dropped all three.

## R-05 — RLS drift between repo and live database (OPEN, MEDIUM)

`pg_policies` reports 70 policies; `supabase/migrations/*.sql` contains 60
`CREATE POLICY` statements. Ten live policies are not reproducible from the
repo.

The migration files are not a complete source of truth for security. Port RLS
from `pg_policies`. Reconcile the drift before cutover, or the gap silently
becomes a permission difference in the new environment.

## R-06 — Extensions unverified against Cloud SQL (OPEN, MEDIUM)

    supabase_vault 0.3.1    Supabase-specific; may hold secrets needing
                            relocation to Secret Manager
    wrappers 0.5.7          Supabase foreign-data wrappers

Confirm what uses each before assuming the schema ports. The other six
extensions (pg_cron, pg_partman, pg_stat_statements, pgcrypto, plpgsql,
uuid-ossp) port cleanly.

## R-07 — Duplicate trading bot via compose (MITIGATED)

`docker compose up -d` would have started a second `trading-bot` container
running the same `main.py` from the same `.env` as `da-trading-bot.service`,
double-writing `bar_log`, `signal_log` and `paper_trades`.

Mitigated by PR #74: the service sits behind the `standalone` profile and its
port is bound to loopback. Reachable deliberately via
`docker compose --profile standalone up -d trading-bot`.

## R-08 — Replicator false-pass on silent failure (MITIGATED)

`sync_once` catches per-table exceptions and returns normally, and returns
early for tables with no rows, so a sweep that replicated nothing exited 0 with
no traceback.

Mitigated by PR #72: the runner refuses to start in mock mode without
`--allow-mock`, counts ERROR records and exits non-zero, and reports per-table
`sync_cursors` movement as ground truth.

## R-09 — Decimal/datetime serialization (MITIGATED)

`json.dumps(row)` raised `TypeError` on the first `bar_log` row because
`bar_time` is `timestamptz` and OHLC columns are `numeric`.

Mitigated by PR #75: `_json_safe_row` converts Decimal to string (BigQuery
NUMERIC accepts a string and round-trips exactly; `float()` would lose price
precision), and datetime/date/time to ISO-8601.
