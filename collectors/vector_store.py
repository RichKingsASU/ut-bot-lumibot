import asyncio
import os
import sys
import json
import logging
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv

# SentenceTransformers and Qdrant
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from collectors.base_collector import BaseCollector

logger = logging.getLogger("VectorStore")

IS_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_NATS_URL = "nats://nats:4222" if IS_DOCKER else "nats://localhost:4222"
QDRANT_HOST = "qdrant" if IS_DOCKER else "localhost"
QDRANT_PORT = 6333

class VectorStoreService(BaseCollector):
    def __init__(self, nats_url: str = DEFAULT_NATS_URL):
        super().__init__(nats_url)
        load_dotenv()
        
        logger.info("Initializing vector store service...")
        
        # Load SentenceTransformer model once at startup
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded")
        
        # Connect to Qdrant
        self.qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    def _get_qdrant_id(self, url: str) -> int:
        """Generate a stable 64-bit integer ID from the URL hash."""
        url_hash = hashlib.md5(url.strip().encode("utf-8")).hexdigest()
        return int(url_hash[:16], 16)

    async def process_message(self, msg):
        """Callback for NATS subscription to sentiment.crypto."""
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except Exception as e:
            logger.error(f"[VECTOR] Failed to parse JSON message: {e}")
            return

        try:
            title = data.get("title", "").strip()
            summary = data.get("summary", "").strip()
            url = data.get("url", "").strip()
            source = data.get("source", "").strip()
            published_at = data.get("published_at", "").strip()
            sentiment_score = data.get("sentiment_score")
            sentiment_label = data.get("sentiment_label")
            sentiment_confidence = data.get("sentiment_confidence")
            
            if not url or not title:
                logger.warning(f"[VECTOR] Article missing url/title. Skipping. url: {url}")
                return
            
            # Generate embedding from: title + " " + summary
            scoring_text = f"{title} {summary}".strip()
            
            # SentenceTransformer encode method is synchronous.
            # Run it in a thread pool to avoid blocking the event loop.
            loop = asyncio.get_running_loop()
            embedding = await loop.run_in_executor(None, lambda: self.encoder.encode(scoring_text).tolist())
            
            # Get integer ID
            point_id = self._get_qdrant_id(url)
            
            # Prepare payload
            created_at = datetime.now(timezone.utc).isoformat()
            
            payload = {
                "title": title,
                "url": url,
                "source": source,
                "published_at": published_at,
                "sentiment_score": sentiment_score,
                "sentiment_label": sentiment_label,
                "sentiment_confidence": sentiment_confidence,
                "created_at": created_at
            }
            
            # Upsert into Qdrant collection crypto_news in executor thread to keep event loop completely free.
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name="crypto_news",
                    points=[
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": payload
                        }
                    ]
                )
            )
            
            logger.info(f"Upserted to Qdrant: {title[:50]}")
            
        except Exception as e:
            logger.error(f"[VECTOR] Error processing article: {e}", exc_info=True)

    async def run(self):
        self._running = True
        
        # Connect NATS
        await self.connect()
        
        # Subscribe to sentiment.crypto NATS subject
        logger.info("Subscribing to sentiment.crypto NATS subject...")
        
        async def message_handler(msg):
            # Process concurrently by spawning tasks
            asyncio.create_task(self.process_message(msg))
            
        await self.nc.subscribe("sentiment.crypto", cb=message_handler)
        logger.info("Subscribed to sentiment.crypto. Listening for messages...")
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        self._running = False
        logger.info("[VECTOR] Stopping Vector Store Service...")
        await self.disconnect()
        logger.info("[VECTOR] Vector Store Service stopped.")

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    service = VectorStoreService()
    try:
        await service.run()
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
