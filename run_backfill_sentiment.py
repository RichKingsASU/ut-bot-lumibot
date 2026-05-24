import asyncio
import logging
import sys
from dotenv import load_dotenv
import requests
import os

from collectors.backfill_sentiment import BackfillSentiment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RunBackfillSentiment")

def send_telegram_startup(message: str, chat_id: str = "8641189809"):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("[TELEGRAM] Missing bot token — skipping startup alert")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("[TELEGRAM] Startup message sent successfully.")
        else:
            logger.warning(f"[TELEGRAM] Message failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        logger.error(f"[TELEGRAM] Error sending message: {e}")

async def main():
    load_dotenv()
    
    # Send Telegram startup alert
    send_telegram_startup("🧠 Historical sentiment backfill started — processing database")
    
    # Initialize and run BackfillSentiment
    backfiller = BackfillSentiment()
    try:
        await backfiller.run()
    except Exception as e:
        logger.error(f"Error in backfiller execution: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested.")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
