import asyncio
import json
import logging
import httpx
from datetime import datetime, timezone
from agents.base_agent import BaseAgent

logger = logging.getLogger("MarketAnalystAgent")

class MarketAnalystAgent(BaseAgent):
    def __init__(self, name="MarketAnalyst", asset_class="crypto", qdrant_host="localhost", qdrant_port=6333, nats_url=None):
        super().__init__(name, qdrant_host, qdrant_port)
        self.asset_class = asset_class
        
        # Load environment variables or fallback to standard URLs based on Docker state
        import os
        is_docker = os.path.exists("/.dockerenv")
        default_nats = "nats://nats:4222" if is_docker else "nats://localhost:4222"
        self.nats_url = nats_url or os.getenv("NATS_URL") or default_nats
        
        default_quest = "http://questdb:9000" if is_docker else "http://localhost:9000"
        self.questdb_url = os.getenv("QUESTDB_URL") or default_quest

    async def analyze(self, regime_summary: dict = None):
        """Perform comprehensive market analysis.
        Returns a market_context dictionary:
        {
            avg_sentiment: float,
            sentiment_label: str,
            top_headlines: [str],
            recent_signals: [dict],
            tick_count: int,
            analysis_timestamp: ISO string
        }
        """
        logger.info("Starting market analysis execution...")
        
        # Step 1: get_recent_sentiment(24)
        sentiment_data = await self.get_recent_sentiment(24, self.asset_class)
        avg_sentiment = sentiment_data.get("avg_score", 0.0)
        sentiment_label = sentiment_data.get("label", "neutral")
        top_headlines = sentiment_data.get("top_headlines", [])
        
        # Step 2: query_supabase("signal_log", limit=10)
        try:
            filters = {}
            if self.asset_class == "crypto":
                filters["symbol"] = "like.%USD%"
            elif self.asset_class == "equities":
                filters["symbol"] = "in.(SPY,IWM,QQQ)"
            recent_signals = await self.query_supabase("signal_log", select="*", filters=filters, limit=10)
        except Exception as e:
            logger.error(f"Error querying signal_log from Supabase: {e}")
            recent_signals = []

        # Step 3: GET http://localhost:9000/exec?query=SELECT+count()+FROM+ticks
        tick_count = 0
        try:
            quest_exec_url = f"{self.questdb_url}/exec"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(quest_exec_url, params={"query": "SELECT count() FROM ticks"})
                if resp.status_code == 200:
                    data = resp.json()
                    dataset = data.get("dataset", [])
                    if dataset and len(dataset) > 0 and len(dataset[0]) > 0:
                        tick_count = int(dataset[0][0])
                else:
                    logger.error(f"QuestDB count query failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Error querying QuestDB for tick count: {e}")
            tick_count = 0

        # Step 4: query_qdrant recent articles from crypto_news
        qdrant_articles = []
        try:
            qdrant_articles = await self.query_qdrant(
                query_text="recent cryptocurrency and digital asset articles market sentiment",
                collection="crypto_news",
                limit=5
            )
            logger.info(f"Retrieved {len(qdrant_articles)} recent news articles from Qdrant crypto_news.")
        except Exception as e:
            logger.error(f"Error querying Qdrant for crypto_news: {e}")
            qdrant_articles = []

        # Step 5: Compose market_context
        analysis_timestamp = datetime.now(timezone.utc).isoformat()
        market_context = {
            "asset_class": self.asset_class,
            "avg_sentiment": avg_sentiment,
            "sentiment_label": sentiment_label,
            "top_headlines": top_headlines,
            "recent_signals": recent_signals,
            "tick_count": tick_count,
            "analysis_timestamp": analysis_timestamp
        }
        
        if regime_summary:
            market_context['current_regime'] = regime_summary.get('overall_regime', 'QUIET')
            market_context['strategy_recommendation'] = regime_summary.get('strategy_recommendation', '')
        else:
            market_context['current_regime'] = 'QUIET'
            market_context['strategy_recommendation'] = ''
        
        # Step 6: Publish to NATS subject agents.market_context (JSON)
        try:
            import nats
            nc = await nats.connect(self.nats_url)
            await nc.publish("agents.market_context", json.dumps(market_context).encode("utf-8"))
            await nc.close()
            logger.info("Successfully published market_context to NATS subject 'agents.market_context'.")
        except Exception as e:
            logger.error(f"Failed to publish market_context to NATS: {e}")

        # Step 7: Upsert to Qdrant agent_memory collection with key "market_context"
        try:
            import hashlib
            loop = asyncio.get_running_loop()
            
            # Generate vector embedding for the string "market_context"
            embedding = await loop.run_in_executor(None, lambda: self._get_embed_model().encode("market_context").tolist())
            
            # Generate a stable 64-bit integer ID for the key "market_context"
            key_hash = hashlib.md5("market_context".encode("utf-8")).hexdigest()
            point_id = int(key_hash[:16], 16)
            
            # Store the data within payload
            payload = {
                "key": "market_context",
                "market_context": market_context,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Upsert Point Struct
            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name="agent_memory",
                    points=[
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": payload
                        }
                    ]
                )
            )
            logger.info("Successfully upserted market_context to Qdrant 'agent_memory' collection.")
        except Exception as e:
            logger.error(f"Failed to upsert market_context to Qdrant: {e}")

        return market_context
