"""
Supabase streaming-data logger.

Fire-and-forget writes to: bar_log, signal_log, paper_trades, sessions.
All public functions are non-blocking (daemon threads) so the trade loop
is never stalled by a slow network call.
"""

import logging
import os
import threading
import uuid
from datetime import datetime

import httpx
import pytz

logger = logging.getLogger("supabase_logger")
ET = pytz.timezone("America/New_York")

# ── Module state ─────────────────────────────────────────────────────────────

_url: str | None = None
_key: str | None = None
_headers: dict = {}
_cumulative_pnl: float = 0.0

SESSION_ID: str = ""


def _init():
    """Lazy-init credentials from env."""
    global _url, _key, _headers
    if _url:
        return
    _url = os.getenv("SUPABASE_URL")
    _key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if _url and _key:
        _headers = {
            "apikey": _key,
            "Authorization": f"Bearer {_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }


def _post(table: str, row: dict):
    """Blocking POST to Supabase REST API. Call from a daemon thread only."""
    _init()
    if not _url or not _key:
        logger.warning("[SUPABASE] Missing credentials — skipping %s write", table)
        return
    try:
        resp = httpx.post(
            f"{_url}/rest/v1/{table}",
            headers=_headers,
            json=row,
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            logger.warning("[SUPABASE] %s write failed (%d): %s",
                           table, resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("[SUPABASE] %s write error: %s", table, e)


def _fire(table: str, row: dict):
    """Spawn a daemon thread for non-blocking write."""
    t = threading.Thread(target=_post, args=(table, row), daemon=True)
    t.start()


# ── Public API ───────────────────────────────────────────────────────────────

def check_connectivity() -> bool:
    """
    Startup connectivity check. Returns True if Supabase is reachable.
    Prints status to log.
    """
    _init()
    if not _url or not _key:
        logger.warning("[SUPABASE] WARNING: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        return False
    try:
        resp = httpx.get(
            f"{_url}/rest/v1/bar_log?select=count",
            headers={**_headers, "Prefer": "count=exact"},
            timeout=10,
        )
        if resp.status_code in (200, 206):
            count = resp.headers.get("content-range", "*/0").split("/")[-1]
            logger.info("[SUPABASE] Connected — bar_log has %s rows", count)
            return True
        elif resp.status_code == 404:
            logger.warning(
                "[SUPABASE] WARNING: Tables not created yet. "
                "Run the SQL in dashboard/supabase/migrations/"
                "20260326000000_streaming_tables.sql in the Supabase SQL Editor."
            )
            return False
        else:
            logger.warning("[SUPABASE] WARNING: Unexpected status %d: %s",
                           resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.warning("[SUPABASE] WARNING: Cannot connect — %s", e)
        return False


def generate_session_id() -> str:
    """Generate a short unique session ID."""
    global SESSION_ID
    SESSION_ID = datetime.now(ET).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    return SESSION_ID


def log_session_start(symbol: str, metadata: dict | None = None):
    """Log session start to the sessions table."""
    row = {
        "session_id": SESSION_ID,
        "symbol": symbol,
        "started_at": datetime.now(ET).isoformat(),
        "status": "running",
        "trades_count": 0,
        "total_pnl": 0,
        "metadata": metadata or {},
    }
    _fire("sessions", row)
    logger.info("[SUPABASE] Session started: %s", SESSION_ID)


def log_session_end():
    """Update session status to 'stopped'."""
    _init()
    if not _url or not _key:
        return
    try:
        resp = httpx.patch(
            f"{_url}/rest/v1/sessions?session_id=eq.{SESSION_ID}",
            headers=_headers,
            json={
                "ended_at": datetime.now(ET).isoformat(),
                "status": "stopped",
                "total_pnl": round(_cumulative_pnl, 2),
            },
            timeout=10,
        )
        if resp.status_code not in (200, 204):
            logger.warning("[SUPABASE] session end update failed: %d %s",
                           resp.status_code, resp.text[:200])
        else:
            logger.info("[SUPABASE] Session ended: %s", SESSION_ID)
    except Exception as e:
        logger.warning("[SUPABASE] session end error: %s", e)


def log_bar(symbol: str, bar: dict):
    """
    Log a completed 1m bar.

    bar should have keys: t (timestamp), o, h, l, c, v
    """
    row = {
        "session_id": SESSION_ID,
        "symbol": symbol,
        "bar_time": bar["t"] if isinstance(bar["t"], str) else bar["t"].isoformat(),
        "open": float(bar["o"]),
        "high": float(bar["h"]),
        "low": float(bar["l"]),
        "close": float(bar["c"]),
        "volume": int(bar.get("v", 0)),
    }
    _fire("bar_log", row)


def log_signal(
    symbol: str,
    bar_time: str,
    timeframe: str,
    signal_type: str,
    close_price: float,
    trail_stop: float,
    atr: float,
    rsi: float | None = None,
    buy_sig: bool = False,
    sell_sig: bool = False,
):
    """Log a UT Bot signal to signal_log."""
    row = {
        "session_id": SESSION_ID,
        "symbol": symbol,
        "bar_time": bar_time,
        "timeframe": timeframe,
        "signal_type": signal_type,
        "close_price": float(close_price),
        "trail_stop": float(trail_stop),
        "atr": float(atr),
        "rsi": float(rsi) if rsi is not None else None,
        "buy_sig": buy_sig,
        "sell_sig": sell_sig,
    }
    _fire("signal_log", row)


def log_trade(
    symbol: str,
    side: str,
    contract_symbol: str | None = None,
    direction: str | None = None,
    option_type: str | None = None,
    strike: float | None = None,
    expiration: str | None = None,
    qty: int | None = None,
    entry_price: float | None = None,
    exit_price: float | None = None,
    entry_underlying_price: float | None = None,
    exit_underlying_price: float | None = None,
    trade_pnl: float | None = None,
    exit_reason: str | None = None,
    entry_rsi: float | None = None,
):
    """
    Log a trade event (ENTRY or EXIT) to paper_trades.

    side='ENTRY' → trade_pnl=None
    side='EXIT'  → trade_pnl filled, cumulative_pnl updated
    """
    global _cumulative_pnl
    if trade_pnl is not None:
        _cumulative_pnl += trade_pnl

    row = {
        "session_id": SESSION_ID,
        "symbol": symbol,
        "contract_symbol": contract_symbol,
        "direction": direction,
        "option_type": option_type,
        "strike": float(strike) if strike is not None else None,
        "expiration": expiration,
        "qty": qty,
        "side": side,
        "entry_price": float(entry_price) if entry_price is not None else None,
        "exit_price": float(exit_price) if exit_price is not None else None,
        "entry_underlying_price": float(entry_underlying_price) if entry_underlying_price is not None else None,
        "exit_underlying_price": float(exit_underlying_price) if exit_underlying_price is not None else None,
        "trade_pnl": round(trade_pnl, 2) if trade_pnl is not None else None,
        "cumulative_pnl": round(_cumulative_pnl, 2),
        "exit_reason": exit_reason,
        "entry_rsi": float(entry_rsi) if entry_rsi is not None else None,
    }
    _fire("paper_trades", row)

    # Also update session trades_count
    _update_session_trades()


def _update_session_trades():
    """Increment trades_count on the session row."""
    _init()
    if not _url or not _key:
        return

    def _do():
        try:
            # Read current count
            resp = httpx.get(
                f"{_url}/rest/v1/sessions?session_id=eq.{SESSION_ID}&select=trades_count",
                headers={**_headers, "Prefer": ""},
                timeout=10,
            )
            if resp.status_code == 200 and resp.json():
                current = resp.json()[0].get("trades_count", 0) or 0
                httpx.patch(
                    f"{_url}/rest/v1/sessions?session_id=eq.{SESSION_ID}",
                    headers=_headers,
                    json={
                        "trades_count": current + 1,
                        "total_pnl": round(_cumulative_pnl, 2),
                    },
                    timeout=10,
                )
        except Exception as e:
            logger.warning("[SUPABASE] session update error: %s", e)

    t = threading.Thread(target=_do, daemon=True)
    t.start()
