import asyncio
import logging
import signal
import sys
from dotenv import load_dotenv

from hermes.health_watcher import HealthWatcher
from hermes.news_collector import NewsCollector
import adapters.telegram_alerts as telegram_alerts

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("HermesMain")

async def main():
    load_dotenv()
    logger.info("Starting Hermes Observer Layer...")
    telegram_alerts.send_alert("🟢 Hermes observer online. Agents: health_watcher, news_collector")

    watcher = HealthWatcher()
    collector = NewsCollector()

    try:
        await asyncio.gather(
            watcher.start(),
            collector.start()
        )
    except asyncio.CancelledError:
        logger.info("Gather cancelled.")
    finally:
        logger.info("Hermes Observer Layer offline.")
        telegram_alerts.send_alert("🔴 Hermes observer offline.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
