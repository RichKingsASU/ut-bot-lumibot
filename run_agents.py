"""
run_agents.py — Disrupting Alpha v2 Phase 4
Entry point: sends Telegram startup notification, then runs the LangGraph
orchestrator pipeline every 15 minutes indefinitely.

Usage:
    python run_agents.py
"""

import asyncio
import logging
import os
import sys

import httpx
from dotenv import load_dotenv

# ── Bootstrap ──────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("RunAgents")

_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8641189809")

_CYCLE_INTERVAL_SECONDS = 900  # 15 minutes


# ── Telegram helper ────────────────────────────────────────────────────────────

async def _send_telegram(text: str, chat_id: str = _TELEGRAM_CHAT_ID) -> None:
    """Send a Telegram message (best-effort, never raises)."""
    token = _TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram startup message sent successfully.")
            else:
                logger.error(f"Telegram send failed: {resp.status_code} — {resp.text}")
    except Exception as exc:
        logger.error(f"Telegram send exception: {exc}")


# ── Main loop ──────────────────────────────────────────────────────────────────

async def main() -> None:
    """Send startup notification, then run the orchestrator pipeline every 15 min."""
    # Import after load_dotenv so agents pick up env vars
    from agents.orchestrator import run_cycle

    startup_message = (
        "🤖 Agent orchestrator started — LangGraph pipeline every 15min"
    )
    await _send_telegram(startup_message, chat_id="8641189809")
    logger.info(startup_message)

    cycle_count = 0
    while True:
        cycle_count += 1
        logger.info(f"[RunAgents] ── Starting cycle #{cycle_count} ──")
        try:
            await run_cycle()
            logger.info(f"[RunAgents] ── Cycle #{cycle_count} complete ──")
        except Exception as exc:
            logger.error(f"[RunAgents] Cycle #{cycle_count} raised an exception: {exc}", exc_info=True)

        logger.info(
            f"[RunAgents] Sleeping {_CYCLE_INTERVAL_SECONDS}s until next cycle..."
        )
        await asyncio.sleep(_CYCLE_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
