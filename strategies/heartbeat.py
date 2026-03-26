"""
Bot heartbeat — writes status to Supabase every 30 seconds.

Uses httpx fire-and-forget via a background thread so the trade loop
is NEVER blocked. On clean shutdown (SIGINT/SIGTERM), writes
status='offline' before exiting.
"""

import atexit
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("heartbeat")

# ── Module state ─────────────────────────────────────────────────────────────
SESSION_ID = str(uuid.uuid4())
_start_time = time.monotonic()
_stop_event = threading.Event()
_heartbeat_thread: threading.Thread | None = None
_last_signal: str | None = None
_last_signal_time: str | None = None

HEARTBEAT_INTERVAL = 30  # seconds


def _supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "")


def _supabase_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def _symbol() -> str:
    return os.getenv("TRADING_SYMBOL", "SPY")


def _mode() -> str:
    is_paper = os.getenv("ALPACA_IS_PAPER", "true").lower()
    return "paper" if is_paper == "true" else "live"


def set_last_signal(signal: str | None, signal_time: str | None = None):
    """Called from the strategy when a new signal fires."""
    global _last_signal, _last_signal_time
    _last_signal = signal
    _last_signal_time = signal_time or datetime.now(timezone.utc).isoformat()


def _upsert_status(status: str = "online"):
    """Fire-and-forget upsert to Supabase bot_status table via REST."""
    url = _supabase_url()
    key = _supabase_key()
    if not url or not key:
        return

    uptime = int(time.monotonic() - _start_time)
    payload = {
        "id": 1,
        "status": status,
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "session_id": SESSION_ID,
        "symbol": _symbol(),
        "mode": _mode(),
        "uptime_seconds": uptime,
        "last_signal": _last_signal,
        "last_signal_time": _last_signal_time,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        import httpx
        # Upsert: POST with Prefer: resolution=merge-duplicates
        resp = httpx.post(
            f"{url}/rest/v1/bot_status",
            json=payload,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
            timeout=10,
        )
        if resp.status_code < 300:
            logger.debug("Heartbeat sent (status=%s)", status)
        else:
            logger.warning("Heartbeat HTTP %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("Heartbeat failed (non-blocking): %s", e)


def _heartbeat_loop():
    """Background thread that sends heartbeats every HEARTBEAT_INTERVAL seconds."""
    while not _stop_event.is_set():
        _upsert_status("online")
        _stop_event.wait(HEARTBEAT_INTERVAL)


def start():
    """Start the heartbeat background thread. Safe to call multiple times."""
    global _heartbeat_thread
    if _heartbeat_thread is not None and _heartbeat_thread.is_alive():
        return

    _stop_event.clear()
    _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True, name="heartbeat")
    _heartbeat_thread.start()
    logger.info("Heartbeat started (session=%s, interval=%ds)", SESSION_ID, HEARTBEAT_INTERVAL)

    # Send first heartbeat immediately
    threading.Thread(target=_upsert_status, args=("online",), daemon=True).start()


def stop():
    """Stop heartbeat and write offline status. Called on shutdown."""
    _stop_event.set()
    if _heartbeat_thread is not None:
        _heartbeat_thread.join(timeout=5)
    # Final offline write — blocking because we're shutting down
    _upsert_status("offline")
    logger.info("Heartbeat stopped — offline status written")


# Register atexit so even unhandled exits attempt an offline write
atexit.register(stop)
