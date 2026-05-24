import abc
import os
import asyncio
import logging
import httpx
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

logger = logging.getLogger("BaseAgent")

class BaseAgent(abc.ABC):
    _embed_model = None

    def __init__(self, name, qdrant_host="localhost", qdrant_port=6333):
        self.name = name
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        
        # Load environment variables
        load_dotenv()
        self.supabase_url = os.getenv("SUPABASE_URL")
        # Support fallback to service role key if anon key is not defined explicitly
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.alpaca_api_key = os.getenv("ALPACA_API_KEY")
        self.alpaca_api_secret = os.getenv("ALPACA_API_SECRET")
        self.alpaca_base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        
        # Connect to Qdrant client
        from qdrant_client import QdrantClient
        self.qdrant_client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        
        # Ensure embedding model is loaded once at the class level
        BaseAgent._get_embed_model()

    @classmethod
    def _get_embed_model(cls):
        if cls._embed_model is None:
            logger.info("Loading SentenceTransformer model 'all-MiniLM-L6-v2' at class level...")
            from sentence_transformers import SentenceTransformer
            cls._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded successfully.")
        return cls._embed_model

    async def query_qdrant(self, query_text, collection, limit=5):
        """Generates embedding with SentenceTransformer all-MiniLM-L6-v2 and searches Qdrant, returning list of payloads."""
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(None, lambda: self._get_embed_model().encode(query_text).tolist())
        
        results = await loop.run_in_executor(
            None,
            lambda: self.qdrant_client.search(
                collection_name=collection,
                query_vector=embedding,
                limit=limit
            )
        )
        return [res.payload for res in results]

    async def query_supabase(self, table, select="*", filters=None, limit=10):
        """httpx GET to SUPABASE_URL/rest/v1/{table} with apikey header, returning list of rows."""
        if not self.supabase_url or not self.supabase_anon_key:
            logger.error("Supabase credentials missing!")
            return []
            
        url = f"{self.supabase_url}/rest/v1/{table}"
        headers = {
            "apikey": self.supabase_anon_key,
            "Authorization": f"Bearer {self.supabase_anon_key}"
        }
        params = {
            "select": select,
            "limit": limit
        }
        if filters:
            params.update(filters)
            
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_recent_sentiment(self, hours=24):
        """Queries cloud Supabase news_articles via REST API where created_at > now()-interval and sentiment_score IS NOT NULL.
        Returns {avg_score, label, top_headlines}
        label: avg>0.2="bullish", avg<-0.2="bearish", else="neutral"
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        filters = {
            "created_at": f"gt.{cutoff}",
            "sentiment_score": "not.is.null",
            "order": "created_at.desc"
        }
        
        try:
            # Fetch up to 100 recent articles within the timeframe to evaluate overall sentiment
            rows = await self.query_supabase(
                table="news_articles",
                select="title,sentiment_score",
                filters=filters,
                limit=100
            )
        except Exception as e:
            logger.error(f"Error querying sentiment from Supabase: {e}")
            return {
                "avg_score": 0.0,
                "label": "neutral",
                "top_headlines": []
            }
            
        if not rows:
            return {
                "avg_score": 0.0,
                "label": "neutral",
                "top_headlines": []
            }
            
        scores = [float(row["sentiment_score"]) for row in rows if row.get("sentiment_score") is not None]
        
        if not scores:
            return {
                "avg_score": 0.0,
                "label": "neutral",
                "top_headlines": []
            }
            
        avg_score = sum(scores) / len(scores)
        
        if avg_score > 0.2:
            label = "bullish"
        elif avg_score < -0.2:
            label = "bearish"
        else:
            label = "neutral"
            
        top_headlines = [row["title"] for row in rows if row.get("title")][:5]
        
        return {
            "avg_score": avg_score,
            "label": label,
            "top_headlines": top_headlines
        }

    @abc.abstractmethod
    async def analyze(self):
        """Abstract method to be implemented by subclassing agents."""
        pass
