import asyncio
import logging
import sys
from dotenv import load_dotenv

from collectors.news_collector import NewsCollector
from adapters.telegram_alerts import send_alert

# Setup basic logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RunNewsCollector")

async def main():
    load_dotenv()
    
    # Send Telegram Startup message
    startup_msg = "🚀 News Collector Starting Live (Finnhub + RSS → NATS)"
    logger.info(f"Sending Telegram startup message: {startup_msg}")
    send_alert(startup_msg)
    
    # Start News Collector
    collector = NewsCollector()
    try:
        await collector.run()
    except asyncio.CancelledError:
        logger.info("Asyncio task cancelled.")
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
    finally:
        await collector.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested via KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"Unhandled exception in news collector: {e}", exc_info=True)
