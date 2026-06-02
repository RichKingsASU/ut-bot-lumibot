import asyncio
import os
import sys
import json
import logging
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv

# HuggingFace transformers
from transformers import pipeline

from collectors.base_collector import BaseCollector

logger = logging.getLogger("SentimentScorer")

# Smart docker/localhost detection
IS_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_NATS_URL = "nats://nats:4222" if IS_DOCKER else "nats://localhost:4222"

class SentimentScorer(BaseCollector):
    def __init__(self, nats_url: str = DEFAULT_NATS_URL):
        super().__init__(nats_url)
        load_dotenv()
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        self.http_client = httpx.AsyncClient(timeout=15.0)
        self.semaphore = asyncio.Semaphore(4)
        
        logger.info("Initializing FinBERT sentiment scorer...")
        # Load pipeline once at startup
        self.classifier = pipeline("text-classification", model="ProsusAI/finbert")
        logger.info("FinBERT model loaded")

    async def _update_supabase_sentiment(self, url: str, sentiment_score: float) -> bool:
        """Update sentiment_score in cloud Supabase news_articles table WHERE url = article url."""
        if not self.supabase_url or not self.supabase_key:
            logger.warning("[SCORER] Supabase credentials missing. Skipping DB update.")
            return False
            
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        try:
            # PostgREST PATCH WHERE url = eq.<url>
            params = {"url": f"eq.{url}"}
            resp = await self.http_client.patch(
                f"{self.supabase_url}/rest/v1/news_articles",
                headers=headers,
                params=params,
                json={"sentiment_score": sentiment_score},
                timeout=10.0
            )
            if resp.status_code in (200, 204):
                return True
            else:
                logger.warning(f"[SCORER] Supabase PATCH failed for {url} ({resp.status_code}): {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"[SCORER] Supabase PATCH error for {url}: {e}")
            return False

    async def process_message(self, msg):
        """Callback for NATS subscription to news.crypto and news.equities."""
        # Use semaphore to limit to max 4 concurrent tasks
        async with self.semaphore:
            try:
                data = json.loads(msg.data.decode("utf-8"))
            except Exception as e:
                logger.error(f"[SCORER] Failed to parse JSON message: {e}")
                return

            try:
                title = data.get("title", "").strip()
                summary = data.get("summary", "").strip()
                url = data.get("url", "").strip()
                asset_class = (data.get("asset_class") or "crypto").strip()
                
                if not url:
                    logger.warning("[SCORER] Article has no URL. Skipping.")
                    return
                
                # Combine title and summary
                scoring_text = f"{title} {summary}".strip()
                if not scoring_text:
                    logger.warning(f"[SCORER] Empty text for scoring on url: {url}")
                    return
                
                # Run classification: truncate to 512 tokens max
                results = self.classifier(scoring_text, truncation=True, max_length=512)
                if not results:
                    logger.warning(f"[SCORER] Classification returned empty results for: {title[:30]}")
                    return
                
                result = results[0]
                label = result.get("label", "neutral").lower()
                confidence = result.get("score", 0.0)
                
                # Map labels: positive=1.0, negative=-1.0, neutral=0.0
                if label == "positive":
                    label_value = 1.0
                elif label == "negative":
                    label_value = -1.0
                else:
                    label_value = 0.0
                    
                sentiment_score = label_value * confidence
                
                # Update sentiment_score in Supabase
                await self._update_supabase_sentiment(url, sentiment_score)
                
                # Enrich article payload
                enriched_article = dict(data)
                enriched_article.update({
                    "sentiment_score": sentiment_score,
                    "sentiment_label": label,
                    "sentiment_confidence": confidence
                })
                
                # Publish enriched article to sentiment.<asset_class> (sentiment.crypto / sentiment.equities)
                await self.publish(f"sentiment.{asset_class}", enriched_article)
                
                # Log scored article: title, score, label, confidence
                logger.info(
                    f"[SCORER] Scored: \"{title[:50]}...\" | Score: {sentiment_score:.4f} | "
                    f"Label: {label} | Conf: {confidence:.4f}"
                )
                
            except Exception as e:
                logger.error(f"[SCORER] Error processing article: {e}", exc_info=True)

    async def run(self):
        self._running = True
        
        # Connect NATS
        await self.connect()
        
        # Subscribe to news.crypto and news.equities NATS subjects
        logger.info("Subscribing to news.crypto and news.equities NATS subjects...")

        async def message_handler(msg):
            # Create a task to process message concurrently (using semaphore internally)
            asyncio.create_task(self.process_message(msg))

        await self.nc.subscribe("news.crypto", cb=message_handler)
        await self.nc.subscribe("news.equities", cb=message_handler)
        logger.info("Subscribed to news.crypto and news.equities. Listening for messages...")
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        self._running = False
        logger.info("[SCORER] Stopping Sentiment Scorer...")
        await self.http_client.aclose()
        await self.disconnect()
        logger.info("[SCORER] Sentiment Scorer stopped.")

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    scorer = SentimentScorer()
    try:
        await scorer.run()
    except KeyboardInterrupt:
        await scorer.stop()

if __name__ == "__main__":
    asyncio.run(main())
