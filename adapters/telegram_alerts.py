import logging
import os
import sys
import threading
import requests
import inspect
import adapters.supabase_logger as db
from common.supabase_auth import get_supabase_headers

logger = logging.getLogger("telegram_outbox")

_token: str | None = None
_chat_id: str | None = None

def _init():
    """Lazy-init credentials from env."""
    global _token, _chat_id
    if _token:
        return
    _token = os.getenv("TELEGRAM_BOT_TOKEN")
    _chat_id = os.getenv("TELEGRAM_CHAT_ID")


def _resolve_message_type(message: str) -> str:
    """Best-effort classification of an outbound message body.

    Maps to the telegram_outbox.message_type domain: 'cycle_report' | 'alert' |
    'other'. Heuristic only — never raises.
    """
    caller = "unknown"
    try:
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_back:
            caller = frame.f_back.f_back.f_code.co_name
    except Exception:
        pass
    logger.warning("Fallback _resolve_message_type called by %s", caller)
    text = message or ""
    upper = text.upper()
    if "EOD" in upper or "SUMMARY" in upper or "HEARTBEAT" in upper or "💓" in text:
        return "cycle_report"
    if "🚨" in text or "ERROR" in upper or "ALERT" in upper or "⚠" in text:
        return "alert"
    return "other"


def _tee_outbox(body: str, chat_id, send_ok: bool, telegram_message_id, error, message_type: str | None = None):
    """Record one row in the Supabase telegram_outbox audit table.

    Fire-and-forget audit tee. This MUST NOT raise: a failure to record the
    audit row must never affect (or mask) the outer send path. Any problem is
    logged at WARNING and swallowed. Reads the service key from either
    SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY (migration in progress).
    """
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            logger.warning("[TELEGRAM] outbox tee skipped — Supabase credentials not set")
            return
        row = {
            "chat_id": str(chat_id) if chat_id else "unknown",
            "message_type": message_type if message_type else _resolve_message_type(body),
            "body": body,
            "telegram_message_id": telegram_message_id,
            "send_ok": bool(send_ok),
            "error": error,
        }
        from common.safe_write import safe_write_sync
        safe_write_sync(
            table="telegram_outbox",
            payload=row,
            component="telegram_outbox_tee",
            method="post",
            upsert=False,
            _url=url,
            _key=key
        )
    except Exception as e:
        logger.error("[TELEGRAM] outbox tee error: %s", e)


def _send(message: str, message_type: str | None = None):
    """Blocking POST to Telegram sendMessage API. Call from a daemon thread only."""
    _init()
    if not _token or not _chat_id:
        print("[TELEGRAM] Missing credentials — skipping message dispatch", file=sys.stderr)
        # A skipped dispatch is still an absence worth recording: leave a trace.
        _tee_outbox(message, _chat_id, False, None, "telegram credentials not configured", message_type=message_type)
        return
    url = f"https://api.telegram.org/bot{_token}/sendMessage"
    payload = {
        "chat_id": _chat_id,
        "text": message
    }
    send_ok = False
    telegram_message_id = None
    error = None
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            send_ok = True
            try:
                telegram_message_id = (resp.json() or {}).get("result", {}).get("message_id")
            except Exception:
                telegram_message_id = None
        else:
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            print(f"[TELEGRAM] Message failed ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
    except Exception as e:
        error = str(e)
        print(f"[TELEGRAM] Error sending message: {e}", file=sys.stderr)

    # Tee the outcome (success OR failure) to the outbox audit table. A failed
    # send must leave a trace with send_ok=false and the error populated.
    _tee_outbox(message, _chat_id, send_ok, telegram_message_id, error, message_type=message_type)

def _fire(message: str, message_type: str):
    """Spawn a daemon thread for non-blocking write."""
    t = threading.Thread(target=_send, args=(message, message_type), daemon=True)
    t.start()

def send_alert(message: str):
    """Public function to fire a Telegram alert in a non-blocking daemon thread."""
    try:
        _fire(message, "alert")
    except Exception as e:
        print(f"[TELEGRAM] send_alert failed to spawn thread: {e}", file=sys.stderr)

def send_startup():
    """Public function to send bot startup details."""
    try:
        symbol = os.getenv("TRADING_SYMBOL", "SPY")
        session_id = getattr(db, "SESSION_ID", "UNKNOWN")
        msg = f"🚀 DisruptingAlpha BOT STARTED\nStrategy: UTBotStrategy\nMode: PAPER\nSymbol: {symbol}\nSession: {session_id}"
        _fire(msg, "other")
    except Exception as e:
        print(f"[TELEGRAM] send_startup error: {e}", file=sys.stderr)

def send_signal(symbol: str, side: str, price: float, rsi: float, atr: float):
    """Public function to send a UT Bot signal alert."""
    try:
        msg = f"📊 SIGNAL: {side.upper()} {symbol}\nPrice: ${price}\nRSI: {rsi}\nATR: {atr}"
        _fire(msg, "alert")
    except Exception as e:
        print(f"[TELEGRAM] send_signal error: {e}", file=sys.stderr)

def send_trade_entry(symbol: str, direction: str, qty: float, price: float):
    """Public function to send a trade entry alert."""
    try:
        msg = f"✅ ENTRY: {direction.upper()} {qty}x {symbol}\nUnderlying: ${price}"
        _fire(msg, "other")
    except Exception as e:
        print(f"[TELEGRAM] send_trade_entry error: {e}", file=sys.stderr)

def send_trade_exit(symbol: str, direction: str, pnl: float, reason: str):
    """Public function to send a trade exit alert."""
    try:
        msg = f"💰 EXIT: {symbol}\nP&L: ${pnl}\nReason: {reason}"
        _fire(msg, "other")
    except Exception as e:
        print(f"[TELEGRAM] send_trade_exit error: {e}", file=sys.stderr)

def send_heartbeat(session_id: str, uptime_mins: int):
    """Public function to send a bot heartbeat alert."""
    try:
        msg = f"💓 Heartbeat\nSession: {session_id}\nUptime: {uptime_mins}m"
        _fire(msg, "cycle_report")
    except Exception as e:
        print(f"[TELEGRAM] send_heartbeat error: {e}", file=sys.stderr)

def send_error(error_msg: str):
    """Public function to send an error alert."""
    try:
        msg = f"🚨 ERROR\n{error_msg}"
        _fire(msg, "alert")
    except Exception as e:
        print(f"[TELEGRAM] send_error error: {e}", file=sys.stderr)

def send_eod_summary(trades: int, pnl: float, win_rate: float):
    """Public function to send an End-Of-Day trading summary alert."""
    try:
        msg = f"📈 EOD SUMMARY\nTrades: {trades}\nP&L: ${pnl}\nWin Rate: {win_rate}%"
        _fire(msg, "cycle_report")
    except Exception as e:
        print(f"[TELEGRAM] send_eod_summary error: {e}", file=sys.stderr)

def check_connectivity() -> bool:
    """Startup connectivity check. Returns True if Telegram is reachable."""
    _init()
    if not _token or not _chat_id:
        print("[TELEGRAM] WARNING: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set", file=sys.stderr)
        return False
    try:
        url = f"https://api.telegram.org/bot{_token}/getMe"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            print("[TELEGRAM] Connected — Bot credentials verified", file=sys.stderr)
            return True
        else:
            print(f"[TELEGRAM] WARNING: Invalid bot token ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[TELEGRAM] WARNING: Cannot connect — {e}", file=sys.stderr)
        return False
