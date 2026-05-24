import os
import sys
import json
import logging
import asyncio
import hashlib
import httpx
from datetime import datetime, timezone
from dotenv import load_dotenv
from transformers import pipeline
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BackfillSentiment")

IS_DOCKER = os.path.exists("/.dockerenv")
DEFAULT_QDRANT_HOST = "qdrant" if IS_DOCKER else "localhost"

class BackfillSentiment:
    def __init__(self, qdrant_host: str = DEFAULT_QDRANT_HOST, qdrant_port: int = 6333):
        load_dotenv()
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port

        if not self.supabase_url or not self.supabase_key:
            logger.critical("Supabase credentials missing in .env file!")
            sys.exit(1)

        # Connect to Qdrant Client
        logger.info(f"Connecting to Qdrant at {self.qdrant_host}:{self.qdrant_port}...")
        self.qdrant_client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)

        # Load models once
        logger.info("Loading FinBERT model ProsusAI/finbert...")
        self.classifier = pipeline("text-classification", model="ProsusAI/finbert")
        logger.info("FinBERT model loaded")

        logger.info("Loading embedding model all-MiniLM-L6-v2...")
        self.embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded")

        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.semaphore = asyncio.Semaphore(4)

    def _get_qdrant_id(self, url: str) -> int:
        """Generate a stable 64-bit integer ID from the URL hash."""
        url_hash = hashlib.md5(url.strip().encode("utf-8")).hexdigest()
        return int(url_hash[:16], 16)

    async def fetch_pending_articles(self):
        """Fetch all news articles from Supabase where sentiment_score IS NULL."""
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.supabase_url}/rest/v1/news_articles"
        params = {
            "sentiment_score": "is.null",
            "select": "title,url,source,published_at,summary"
        }
        
        logger.info("Fetching articles with missing sentiment scores from Supabase...")
        resp = await self.http_client.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            articles = resp.json()
            logger.info(f"Found {len(articles)} pending articles to backfill.")
            return articles
        else:
            logger.error(f"Failed to fetch articles from Supabase: {resp.status_code} - {resp.text[:200]}")
            return []

    async def _update_supabase_sentiment(self, url: str, sentiment_score: float) -> bool:
        """Update sentiment_score in cloud Supabase news_articles table."""
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        try:
            resp = await self.http_client.patch(
                f"{self.supabase_url}/rest/v1/news_articles",
                headers=headers,
                params={"url": f"eq.{url}"},
                json={"sentiment_score": sentiment_score}
            )
            return resp.status_code in (200, 201, 204)
        except Exception as e:
            logger.error(f"Supabase patch error: {e}")
            return False

    async def process_single_article(self, article: dict):
        """Perform sentiment scoring and Qdrant upsert for a single article."""
        async with self.semaphore:
            try:
                title = article.get("title", "").strip()
                summary = article.get("summary", "").strip()
                url = article.get("url", "").strip()
                source = article.get("source", "").strip()
                published_at = article.get("published_at", "").strip()

                if not url or not title:
                    return

                scoring_text = f"{title} {summary}".strip()
                if not scoring_text:
                    logger.warning(f"Empty text for article URL {url}")
                    return

                # Sentiment Scoring (FinBERT)
                results = self.classifier(scoring_text, truncation=True, max_length=512)
                if not results:
                    return
                result = results[0]
                label = result.get("label", "neutral").lower()
                confidence = result.get("score", 0.0)

                if label == "positive":
                    label_value = 1.0
                elif label == "negative":
                    label_value = -1.0
                else:
                    label_value = 0.0

                sentiment_score = label_value * confidence

                # Update Supabase
                await self._update_supabase_sentiment(url, sentiment_score)

                # Generate Embedding in thread pool
                loop = asyncio.get_running_loop()
                embedding = await loop.run_in_executor(None, lambda: self.embed_model.encode(scoring_text).tolist())

                # Upsert into Qdrant in executor
                point_id = self._get_qdrant_id(url)
                created_at = datetime.now(timezone.utc).isoformat()
                
                payload = {
                    "title": title,
                    "url": url,
                    "source": source,
                    "published_at": published_at,
                    "sentiment_score": sentiment_score,
                    "sentiment_label": label,
                    "sentiment_confidence": confidence,
                    "created_at": created_at
                }

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

                logger.info(f"Successfully backfilled and indexed: '{title[:40]}' | Score: {sentiment_score:.4f}")

            except Exception as e:
                logger.error(f"Error backfilling article: {e}")

    async def run(self):
        articles = await self.fetch_pending_articles()
        if not articles:
            logger.info("No articles to backfill.")
            await self.http_client.aclose()
            return

        tasks = [self.process_single_article(art) for art in articles]
        await asyncio.gather(*tasks)
        logger.info("Sentiment backfill and index process complete!")
        await self.http_client.aclose()

async def main():
    backfiller = BackfillSentiment()
    await backfiller.run()

if __name__ == "__main__":
    asyncio.run(main())
