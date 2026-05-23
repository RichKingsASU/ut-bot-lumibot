import os
import sys
import threading
import requests
import adapters.supabase_logger as db

_token: str | None = None
_chat_id: str | None = None

def _init():
    """Lazy-init credentials from env."""
    global _token, _chat_id
    if _token:
        return
    _token = os.getenv("TELEGRAM_BOT_TOKEN")
    _chat_id = os.getenv("TELEGRAM_CHAT_ID")

def _send(message: str):
    """Blocking POST to Telegram sendMessage API. Call from a daemon thread only."""
    _init()
    if not _token or not _chat_id:
        print("[TELEGRAM] Missing credentials — skipping message dispatch", file=sys.stderr)
        return
    url = f"https://api.telegram.org/bot{_token}/sendMessage"
    payload = {
        "chat_id": _chat_id,
        "text": message
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[TELEGRAM] Message failed ({resp.status_code}): {resp.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[TELEGRAM] Error sending message: {e}", file=sys.stderr)

def _fire(message: str):
    """Spawn a daemon thread for non-blocking write."""
    t = threading.Thread(target=_send, args=(message,), daemon=True)
    t.start()

def send_alert(message: str):
    """Public function to fire a Telegram alert in a non-blocking daemon thread."""
    try:
        _fire(message)
    except Exception as e:
        print(f"[TELEGRAM] send_alert failed to spawn thread: {e}", file=sys.stderr)

def send_startup():
    """Public function to send bot startup details."""
    try:
        symbol = os.getenv("TRADING_SYMBOL", "SPY")
        session_id = getattr(db, "SESSION_ID", "UNKNOWN")
        msg = f"🚀 DisruptingAlpha BOT STARTED\nStrategy: UTBotStrategy\nMode: PAPER\nSymbol: {symbol}\nSession: {session_id}"
        _fire(msg)
    except Exception as e:
        print(f"[TELEGRAM] send_startup error: {e}", file=sys.stderr)

def send_signal(symbol: str, side: str, price: float, rsi: float, atr: float):
    """Public function to send a UT Bot signal alert."""
    try:
        msg = f"📊 SIGNAL: {side.upper()} {symbol}\nPrice: ${price}\nRSI: {rsi}\nATR: {atr}"
        _fire(msg)
    except Exception as e:
        print(f"[TELEGRAM] send_signal error: {e}", file=sys.stderr)

def send_trade_entry(symbol: str, direction: str, qty: float, price: float):
    """Public function to send a trade entry alert."""
    try:
        msg = f"✅ ENTRY: {direction.upper()} {qty}x {symbol}\nUnderlying: ${price}"
        _fire(msg)
    except Exception as e:
        print(f"[TELEGRAM] send_trade_entry error: {e}", file=sys.stderr)

def send_trade_exit(symbol: str, direction: str, pnl: float, reason: str):
    """Public function to send a trade exit alert."""
    try:
        msg = f"💰 EXIT: {symbol}\nP&L: ${pnl}\nReason: {reason}"
        _fire(msg)
    except Exception as e:
        print(f"[TELEGRAM] send_trade_exit error: {e}", file=sys.stderr)

def send_heartbeat(session_id: str, uptime_mins: int):
    """Public function to send a bot heartbeat alert."""
    try:
        msg = f"💓 Heartbeat\nSession: {session_id}\nUptime: {uptime_mins}m"
        _fire(msg)
    except Exception as e:
        print(f"[TELEGRAM] send_heartbeat error: {e}", file=sys.stderr)

def send_error(error_msg: str):
    """Public function to send an error alert."""
    try:
        msg = f"🚨 ERROR\n{error_msg}"
        _fire(msg)
    except Exception as e:
        print(f"[TELEGRAM] send_error error: {e}", file=sys.stderr)

def send_eod_summary(trades: int, pnl: float, win_rate: float):
    """Public function to send an End-Of-Day trading summary alert."""
    try:
        msg = f"📈 EOD SUMMARY\nTrades: {trades}\nP&L: ${pnl}\nWin Rate: {win_rate}%"
        _fire(msg)
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
