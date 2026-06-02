"""
Component-level heartbeats — ADDITIVE to the global bot_status heartbeat.

The single global heartbeat (bot_status row id=1, written by main via
strategies/heartbeat.py) cannot detect PARTIAL failure: run_agents can die
while main keeps the global heartbeat fresh (or vice versa). Each long-running
process therefore also upserts its own row, keyed on process_name, to the
Supabase `component_status` table so the watchdog can detect per-process
staleness.

Fire-and-forget via a daemon thread so caller loops are NEVER blocked. Mirrors
the pattern already used in strategies/heartbeat.py and adapters/supabase_logger.py.

Supabase DDL for the component_status table is NOT created here — see
dashboard/supabase/component_status.sql for the schema to apply manually.
"""

import logging
import os
import threading
from datetime import datetime, timezone

logger = logging.getLogger("component_heartbeat")


def _post(payload: dict) -> None:
    """Blocking upsert to component_status. Called from a daemon thread."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return
    try:
        import httpx

        # Upsert on the process_name primary key.
        resp = httpx.post(
            f"{url}/rest/v1/component_status",
            json=payload,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            timeout=10,
        )
        if resp.status_code >= 300:
            logger.warning(
                "Component heartbeat HTTP %d: %s", resp.status_code, resp.text[:200]
            )
    except Exception as e:
        logger.warning("Component heartbeat failed (non-blocking): %s", e)


def beat(
    process_name: str,
    status: str = "ok",
    last_successful_cycle_id=None,
    last_trade_decision_timestamp=None,
    blocking: bool = False,
) -> None:
    """Upsert this process's heartbeat row.

    Fire-and-forget by default (spawns a daemon thread). Only the fields that
    are provided are written, so omitting last_successful_cycle_id on an update
    leaves any previously-stored value untouched.
    """
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "process_name": process_name,
        "last_heartbeat": now,
        "status": status,
        "updated_at": now,
    }
    if last_successful_cycle_id is not None:
        payload["last_successful_cycle_id"] = last_successful_cycle_id
    if last_trade_decision_timestamp is not None:
        payload["last_trade_decision_timestamp"] = last_trade_decision_timestamp

    if blocking:
        _post(payload)
    else:
        threading.Thread(target=_post, args=(payload,), daemon=True).start()
