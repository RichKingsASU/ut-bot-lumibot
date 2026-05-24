import asyncio
import logging
import sys
from dotenv import load_dotenv

from collectors.tick_collector import TickCollector
from collectors.questdb_init import init_questdb_schema
from adapters.telegram_alerts import send_alert

# Setup basic logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RunTickCollector")

async def main():
    load_dotenv()
    
    # 1. Initialize QuestDB Schema
    logger.info("Initializing QuestDB schemas...")
    schema_ok = init_questdb_schema()
    if not schema_ok:
        logger.warning("QuestDB schema initialization failed or QuestDB is offline. Tick collector will still attempt to run.")
        
    # 2. Send Telegram Startup message
    startup_msg = "✅ Task 1 & 2: run_tick_collector.py Starting Live (NATS + QuestDB)"
    logger.info(f"Sending Telegram startup message: {startup_msg}")
    send_alert(startup_msg)
    
    # 3. Start Tick Collector
    collector = TickCollector()
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
        logger.critical(f"Unhandled exception in tick collector: {e}", exc_info=True)
