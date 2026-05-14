import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from alpaca.data.enums import DataFeed
from alpaca.data.live import StockDataStream
from alpaca.data.models import Bar
import httpx

logger = logging.getLogger("alpaca_streamer")

class AlpacaStreamer:
    def __init__(self, symbols=None):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_API_SECRET")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.symbols = symbols or ["IWM", "SPY", "QQQ"]
        
        # Alpaca SDK expects DataFeed enum, not a string
        feed_str = os.getenv("ALPACA_FEED", "sip").lower()
        self.feed = DataFeed.SIP if feed_str == "sip" else DataFeed.IEX
        
        if not self.api_key or not self.api_secret:
            raise ValueError("ALPACA_API_KEY and ALPACA_API_SECRET must be set")
            
        self.stream = StockDataStream(self.api_key, self.api_secret, feed=self.feed)
        self.client = httpx.AsyncClient(timeout=10.0)

    async def _upsert_bar(self, bar: Bar):
        """Send bar data to Supabase."""
        try:
            payload = {
                "symbol": bar.symbol,
                "timeframe": "1Min",
                "ts": bar.timestamp.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "vwap": bar.vwap,
                "trade_count": bar.trade_count,
                "feed": self.feed
            }
            
            resp = await self.client.post(
                f"{self.supabase_url}/rest/v1/ohlcv_bars",
                json=payload,
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates"
                }
            )
            
            if resp.status_code >= 300:
                logger.error(f"Supabase Upsert Failed: {resp.status_code} {resp.text}")
            else:
                logger.debug(f"Streamed bar for {bar.symbol} @ {bar.timestamp}")
                
        except Exception as e:
            logger.error(f"Error in _upsert_bar: {e}")

    async def _on_bar(self, bar):
        # We wrap in a task to not block the stream receiver
        asyncio.create_task(self._upsert_bar(bar))

    async def start(self):
        logger.info(f"Starting Alpaca WebSocket Streamer for {self.symbols} (Feed: {self.feed})...")
        self.stream.subscribe_bars(self._on_bar, *self.symbols)
        
        try:
            await self.stream._run_forever()
        except Exception as e:
            logger.error(f"WebSocket Stream Error: {e}")
            await self.stop()

    async def stop(self):
        logger.info("Stopping Alpaca Streamer...")
        await self.stream.stop()
        await self.client.aclose()

if __name__ == "__main__":
    # For standalone testing
    logging.basicConfig(level=logging.INFO)
    streamer = AlpacaStreamer()
    try:
        asyncio.run(streamer.start())
    except KeyboardInterrupt:
        pass
