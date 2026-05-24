import asyncio
import json
import logging
from abc import ABC, abstractmethod
import nats

logger = logging.getLogger("BaseCollector")

class BaseCollector(ABC):
    def __init__(self, nats_url: str = "nats://localhost:4222"):
        self.nats_url = nats_url
        self.nc = None
        self._running = False

    async def connect(self):
        """Connect to NATS with exponential backoff if it fails."""
        attempt = 0
        while self._running:
            try:
                logger.info(f"Connecting to NATS at {self.nats_url}...")
                self.nc = await nats.connect(
                    self.nats_url,
                    reconnect_time_wait=2,
                    max_reconnect_attempts=-1
                )
                logger.info("Successfully connected to NATS!")
                return
            except Exception as e:
                attempt += 1
                delay = min(60.0, 1.5 ** attempt)
                logger.error(f"NATS connection failed: {e}. Retrying in {delay:.2f}s...")
                await asyncio.sleep(delay)

    async def publish(self, subject: str, data: dict):
        """Publish a dictionary as JSON to a NATS subject."""
        if not self.nc or self.nc.is_closed:
            logger.warning("NATS connection not available. Message not published.")
            return
        try:
            payload = json.dumps(data).encode("utf-8")
            await self.nc.publish(subject, payload)
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")

    async def disconnect(self):
        """Disconnect from NATS."""
        if self.nc and not self.nc.is_closed:
            await self.nc.close()
            logger.info("Disconnected from NATS.")

    @abstractmethod
    async def run(self):
        """Main execution logic for the collector."""
        pass
