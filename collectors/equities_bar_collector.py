import asyncio
import os
import time
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

from collectors.base_collector import BaseCollector
from alpaca.data.live import StockDataStream

logger = logging.getLogger("EquitiesBarCollector")

# Smart docker/localhost detection
IS_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_NATS_URL = "nats://nats:4222" if IS_DOCKER else "nats://localhost:4222"
DEFAULT_QDB_HOST = "questdb" if IS_DOCKER else "localhost"

class EquitiesBarCollector(BaseCollector):
    def __init__(self, nats_url: str = DEFAULT_NATS_URL, qdb_host: str = DEFAULT_QDB_HOST, qdb_port: int = 9009):
        super().__init__(nats_url)
        load_dotenv()
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.symbols = ["SPY", "QQQ", "IWM"]  # The core traded symbols
        
        self.qdb_host = qdb_host
        self.qdb_port = qdb_port
        self.qdb_reader = None
        self.qdb_writer = None
        self.qdb_connected = False
        
        self.bar_count = 0
        self.total_bars = 0
        
        if not self.api_key or not self.api_secret:
            raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")
            
        self.stream = StockDataStream(self.api_key, self.api_secret)

    async def connect_questdb(self):
        attempt = 0
        while self._running:
            try:
                logger.info(f"Connecting to QuestDB ILP at {self.qdb_host}:{self.qdb_port}...")
                self.qdb_reader, self.qdb_writer = await asyncio.open_connection(self.qdb_host, self.qdb_port)
                self.qdb_connected = True
                logger.info("Connected to QuestDB ILP successfully!")
                return
            except Exception as e:
                self.qdb_connected = False
                attempt += 1
                delay = min(60.0, 1.5 ** attempt)
                logger.error(f"QuestDB connection failed: {e}. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

    async def write_questdb(self, line: str):
        if not self.qdb_connected or not self.qdb_writer:
            return
        try:
            self.qdb_writer.write(line.encode("utf-8"))
            await self.qdb_writer.drain()
        except Exception as e:
            logger.error(f"QuestDB write error: {e}. Reconnecting...")
            self.qdb_connected = False
            asyncio.create_task(self.connect_questdb())

    async def _log_throughput_loop(self):
        while self._running:
            await asyncio.sleep(60)
            logger.info(f"[THROUGHPUT] Received {self.bar_count} bars in 60s. Total bars: {self.total_bars}")
            self.bar_count = 0

    async def on_bar(self, bar):
        self.bar_count += 1
        self.total_bars += 1
        
        try:
            symbol_clean = bar.symbol
            open_price = float(bar.open)
            high_price = float(bar.high)
            low_price = float(bar.low)
            close_price = float(bar.close)
            volume = float(bar.volume)
            ts_ns = int(bar.timestamp.timestamp() * 1e9)
            
            # 1. Publish to NATS
            payload = {
                "symbol": symbol_clean,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "timestamp": bar.timestamp.isoformat()
            }
            subject = f"bars.equities.1m.{symbol_clean}"
            asyncio.create_task(self.publish(subject, payload))
            
            # 2. Write to QuestDB
            line = f"ohlcv_1m,symbol={symbol_clean} open={open_price},high={high_price},low={low_price},close={close_price},volume={volume} {ts_ns}\n"
            asyncio.create_task(self.write_questdb(line))
        except Exception as e:
            logger.error(f"Error handling bar update: {e}")

    async def run(self):
        self._running = True
        
        # Start NATS connection
        await self.connect()
        
        # Start QuestDB connection
        asyncio.create_task(self.connect_questdb())
        
        # Start throughput log loop
        asyncio.create_task(self._log_throughput_loop())
        
        # Subscribe to stock bars
        logger.info(f"Subscribing to Stock Bars (1Min) for {self.symbols}...")
        self.stream.subscribe_bars(self.on_bar, *self.symbols)
        
        try:
            await self.stream._run_forever()
        except Exception as e:
            logger.error(f"Alpaca StockDataStream error: {e}")
        finally:
            await self.stop()

    async def stop(self):
        self._running = False
        logger.info("Stopping Equities Bar Collector...")
        try:
            await self.stream.stop()
        except Exception:
            pass
        if self.qdb_writer:
            try:
                self.qdb_writer.close()
                await self.qdb_writer.wait_closed()
            except Exception:
                pass
        await self.disconnect()
        logger.info("Equities Bar Collector stopped.")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    collector = EquitiesBarCollector()
    try:
        await collector.run()
    except KeyboardInterrupt:
        await collector.stop()

if __name__ == "__main__":
    asyncio.run(main())
