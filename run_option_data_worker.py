"""
run_option_data_worker.py
─────────────────────────
Entry-point script for the Options Data Worker.

Startup sequence
----------------
1. Load .env
2. Send Telegram startup notification to TELEGRAM_CHAT_ID
3. asyncio.run(option_data_worker.main())
"""

import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv

# ── Load environment first ────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("OptionDataWorkerRunner")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "8641189809")


# ── Telegram helper ───────────────────────────────────────────────────────────

def _send_telegram_sync(message: str) -> None:
    """Synchronous Telegram send for the pre-asyncio startup phase."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping startup notification")
        return
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
        logger.info("Telegram startup notification sent")
    except Exception as exc:
        logger.error("Telegram startup notification failed: %s", exc)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    startup_msg = (
        "📊 Options data worker started — scanning Greeks for "
        "SPY/QQQ/IWM/NVDA/TSLA/AAPL/MSFT/META/GOOGL"
    )
    logger.info(startup_msg)
    _send_telegram_sync(startup_msg)

    from collectors import option_data_worker
    asyncio.run(option_data_worker.main())
