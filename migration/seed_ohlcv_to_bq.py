#!/usr/bin/env python3
"""
seed_ohlcv_to_bq.py - one-time bulk seed of public.ohlcv_bars into BigQuery.

The da-gcp-replicator daemon is a tail-follower: 100 rows per table per sweep
over streaming inserts. At 1.7M rows that is roughly a day of continuous
streaming, and streaming inserts are billed per GB while load jobs are free.
Bulk history therefore goes through load jobs, and the daemon keeps doing what
it is good at -- following the tail.

ohlcv_bars also has no surrogate id, so the daemon's (created_at, id) cursor
cannot address it at all. The natural key is (symbol, timeframe, ts, feed).

Read-only against Postgres. Appends to BigQuery. Safe to re-run only after
truncating the destination -- it does not deduplicate.

Usage:
    set -a && source .env && set +a
    ./venv/bin/python migration/seed_ohlcv_to_bq.py --dry-run
    ./venv/bin/python migration/seed_ohlcv_to_bq.py
"""

import argparse
import datetime
import decimal
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor
from google.cloud import bigquery
from google.oauth2 import service_account

TABLE = "disruptingalpha.replication_dataset.ohlcv_bars"
SOURCE = "public.ohlcv_bars"
# Rows per load job. Large enough that job overhead is negligible, small enough
# that a failure costs one chunk rather than the whole seed.
CHUNK = 100_000
# Server-side cursor batch. Keeps memory flat regardless of total row count.
FETCH = 10_000


def json_safe(row: dict) -> dict:
    """Decimal -> str (NUMERIC round-trips exactly), datetime -> ISO-8601."""
    out = {}
    for k, v in row.items():
        if isinstance(v, decimal.Decimal):
            out[k] = str(v)
        elif isinstance(v, (datetime.datetime, datetime.date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count and sample only; write nothing")
    ap.add_argument("--limit", type=int, help="cap rows (for a rehearsal on a slice)")
    args = ap.parse_args()

    dsn = os.environ.get("SUPABASE_DSN")
    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not (dsn and key):
        print("[FAIL] SUPABASE_DSN and GOOGLE_APPLICATION_CREDENTIALS must be set")
        return 2

    creds = service_account.Credentials.from_service_account_file(key)
    bq = bigquery.Client(credentials=creds, project="disruptingalpha")

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        # Schema is already defined on the partitioned/clustered table; never
        # let a load job infer and silently widen it.
        autodetect=False,
        schema=bq.get_table(TABLE).schema,
    )

    conn = psycopg2.connect(dsn, connect_timeout=30)
    try:
        with conn.cursor() as c:
            c.execute(f"SELECT count(*) FROM {SOURCE}")
            total = c.fetchone()[0]
        print(f"  source rows : {total:,}")
        print(f"  destination : {TABLE}")
        if args.limit:
            print(f"  limit       : {args.limit:,} (rehearsal)")
        if args.dry_run:
            print("  DRY RUN - nothing written")
            return 0

        # Named cursor => server-side, streams instead of materialising 1.7M rows.
        with conn.cursor(name="ohlcv_seed", cursor_factory=RealDictCursor) as cur:
            cur.itersize = FETCH
            q = f"SELECT symbol, timeframe, ts, open, high, low, close, volume, vwap, trade_count, feed, created_at FROM {SOURCE}"
            if args.limit:
                q += f" LIMIT {args.limit}"
            cur.execute(q)

            buf, sent, jobs = [], 0, 0
            for rec in cur:
                buf.append(json_safe(dict(rec)))
                if len(buf) >= CHUNK:
                    bq.load_table_from_json(buf, TABLE, job_config=job_config).result()
                    sent += len(buf); jobs += 1
                    print(f"  loaded {sent:>9,} / {total:,}  ({jobs} job{'s' if jobs > 1 else ''})")
                    buf = []
            if buf:
                bq.load_table_from_json(buf, TABLE, job_config=job_config).result()
                sent += len(buf); jobs += 1
                print(f"  loaded {sent:>9,} / {total:,}  ({jobs} jobs)")
    finally:
        conn.close()

    dest = bq.get_table(TABLE).num_rows
    print(f"\n  RECONCILE  source={total:,}  destination={dest:,}  diff={dest - total:+,}")
    print("  " + ("PASS" if dest == total else "REVIEW - source is live, small positive drift is expected"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
