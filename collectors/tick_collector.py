import asyncio
import os
import time
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

from collectors.base_collector import BaseCollector
from alpaca.data.live import CryptoDataStream

logger = logging.getLogger("TickCollector")

# Smart docker/localhost detection
IS_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_NATS_URL = "nats://nats:4222" if IS_DOCKER else "nats://localhost:4222"
DEFAULT_QDB_HOST = "questdb" if IS_DOCKER else "localhost"

class TickCollector(BaseCollector):
    def __init__(self, nats_url: str = DEFAULT_NATS_URL, qdb_host: str = DEFAULT_QDB_HOST, qdb_port: int = 9009):
        super().__init__(nats_url)
        load_dotenv()
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.symbols = ["BTC/USD", "ETH/USD", "SOL/USD"]
        
        self.qdb_host = qdb_host
        self.qdb_port = qdb_port
        self.qdb_reader = None
        self.qdb_writer = None
        self.qdb_connected = False
        
        self.tick_count = 0
        self.total_ticks = 0
        
        if not self.api_key or not self.api_secret:
            raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")
            
        self.stream = CryptoDataStream(self.api_key, self.api_secret)

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
            await asyncio.sleep(30)
            tps = self.tick_count / 30.0
            logger.info(f"[THROUGHPUT] Received {self.tick_count} ticks in 30s. Rate: {tps:.2f} ticks/s. Total ticks: {self.total_ticks}")
            self.tick_count = 0

    async def on_trade(self, trade):
        self.tick_count += 1
        self.total_ticks += 1
        
        try:
            symbol_clean = trade.symbol.replace("/", "")
            price = float(trade.price)
            size = float(trade.size)
            ts_ns = int(trade.timestamp.timestamp() * 1e9)
            
            # 1. Publish to NATS
            payload = {
                "symbol": symbol_clean,
                "price": price,
                "size": size,
                "timestamp": trade.timestamp.isoformat()
            }
            subject = f"ticks.crypto.{symbol_clean}"
            asyncio.create_task(self.publish(subject, payload))
            
            # 2. Write to QuestDB
            # ticks,symbol=BTCUSD price=50000.0,size=0.01 {ts_ns}
            line = f"ticks,symbol={symbol_clean} price={price},size={size} {ts_ns}\n"
            asyncio.create_task(self.write_questdb(line))
        except Exception as e:
            logger.error(f"Error handling trade update: {e}")

    async def run(self):
        self._running = True
        
        # Start NATS connection
        await self.connect()
        
        # Start QuestDB connection
        asyncio.create_task(self.connect_questdb())
        
        # Start throughput log loop
        asyncio.create_task(self._log_throughput_loop())
        
        # Subscribe to crypto stream
        logger.info(f"Subscribing to Crypto Trades for {self.symbols}...")
        self.stream.subscribe_trades(self.on_trade, *self.symbols)
        
        try:
            await self.stream._run_forever()
        except Exception as e:
            logger.error(f"Alpaca CryptoStream error: {e}")
        finally:
            await self.stop()

    async def stop(self):
        self._running = False
        logger.info("Stopping Tick Collector...")
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
        logger.info("Tick Collector stopped.")
