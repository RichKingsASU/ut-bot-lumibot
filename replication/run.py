#!/usr/bin/env python3
"""
run.py - Entry point for the GCP replicator.

gcp_replicator_daemon.py exposes only classes; the shipped systemd unit pointed
at `-m replication.gcp_replicator_daemon`, which has no __main__ and exits 0
immediately without replicating anything. This module supplies the missing
entry point for both the supervised one-shot run and the long-running daemon.

Mock-mode guard: the daemon treats a missing SUPABASE_DSN as "offline test" and
silently falls back to the data/primary.db SQLite mock, returning success while
replicating nothing (see _GCPClientWrapper.stream_batch). On a production host
that false pass is worse than a crash, so this runner refuses to start in that
state unless --allow-mock is passed explicitly.
"""

import argparse
import asyncio
import logging
import os
import sqlite3
import sys

from replication.gcp_replicator_daemon import ConfigurationError, GCPReplicationDaemon


def safe_print(message: str, status: str = "INFO"):
    """ASCII-safe terminal output, matching tests/ helpers."""
    marker = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}.get(status, "[INFO]")
    print(f"{marker} {message.encode('ascii', 'replace').decode('ascii')}")


def in_production_mode() -> bool:
    """Mirrors the daemon's own is_prod test (gcp_replicator_daemon.py:153)."""
    return bool(os.environ.get("SUPABASE_DSN")) or bool(os.environ.get("PRODUCTION_MODE"))


class _ErrorCounter(logging.Handler):
    """
    sync_once() catches per-table exceptions and logs them, then returns
    normally -- so a sweep that replicated nothing still exits 0 with no
    traceback. For a supervised test run that is a false pass, so we watch the
    log stream directly and let the exit code reflect what actually happened.
    """

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _read_cursors(state_db_path: str) -> dict:
    """Snapshot each table's replication cursor from the local state DB."""
    try:
        conn = sqlite3.connect(state_db_path)
        try:
            rows = conn.execute(
                "SELECT table_name, last_sync_created_at, last_sync_id FROM sync_cursors"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return {}
    return {r[0]: (r[1], r[2]) for r in rows}


def _report_cursor_movement(before: dict, after: dict, tables) -> None:
    """
    sync_once() breaks out of the table loop on the first failure
    (gcp_replicator_daemon.py:267) and returns early for tables with no pending
    rows (:274), so "no errors" alone never proves data actually moved. Cursor
    advancement is the ground truth, so report it per table.
    """
    safe_print("Cursor movement this sweep:", "INFO")
    for table in tables:
        old, new = before.get(table), after.get(table)
        if new is None:
            safe_print(f"  {table}: NOT REACHED (no cursor row written)", "WARN")
        elif old == new:
            safe_print(f"  {table}: unchanged at id={new[1]} (no new rows, or not reached)", "WARN")
        else:
            safe_print(f"  {table}: advanced to id={new[1]} ts={new[0]}", "PASS")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="replication.run")
    parser.add_argument("--sync-once", action="store_true",
                        help="Run a single replication sweep and exit (supervised test).")
    parser.add_argument("--allow-mock", action="store_true",
                        help="Permit running in offline/mock mode. Never use on a production host.")
    parser.add_argument("--polling-interval", type=float, default=5.0,
                        help="Seconds between sweeps in daemon mode (default: 5.0).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not in_production_mode():
        if not args.allow_mock:
            safe_print("SUPABASE_DSN is not set: the daemon would fall back to the "
                       "data/primary.db mock and report success without replicating "
                       "anything. Refusing to start. Pass --allow-mock to override.", "FAIL")
            return 2
        safe_print("Running in MOCK mode. Results do NOT indicate production readiness.", "WARN")
    else:
        via = "SUPABASE_DSN" if os.environ.get("SUPABASE_DSN") else "PRODUCTION_MODE"
        safe_print(f"Production mode active (via {via}).", "INFO")
        if not os.environ.get("SUPABASE_DSN"):
            safe_print("PRODUCTION_MODE is set but SUPABASE_DSN is not: the daemon will "
                       "read from the local SQLite path while enforcing production GCP "
                       "checks. This is almost certainly not what you want.", "WARN")

    try:
        daemon = GCPReplicationDaemon(polling_interval=args.polling_interval)
    except ConfigurationError as exc:
        safe_print(f"Configuration rejected: {exc}", "FAIL")
        return 1

    if args.sync_once:
        counter = _ErrorCounter()
        logging.getLogger("gcp_replicator").addHandler(counter)
        safe_print("Starting single replication sweep...", "INFO")
        before = _read_cursors(daemon.state_db_path)
        daemon.sync_once()
        _report_cursor_movement(before, _read_cursors(daemon.state_db_path), daemon.tables)
        if counter.records:
            safe_print(f"Sweep finished but logged {len(counter.records)} error(s); "
                       "replication did NOT succeed:", "FAIL")
            for record in counter.records:
                safe_print(f"  - {record.getMessage()}", "FAIL")
            return 1
        safe_print("Sweep complete with no errors.", "PASS")
        return 0

    safe_print("Starting continuous replication loop (Ctrl-C to stop)...", "INFO")
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        safe_print("Interrupted; shutting down.", "INFO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
