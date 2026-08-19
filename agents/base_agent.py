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

    def __init__(self, name, qdrant_host="localhost", qdrant_port=6333,
                 qdrant_client=None, embed_model=None):
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
        
        # Unit-test and alternate-runtime collaborators may be injected without
        # importing or initializing the optional model/storage dependencies.
        if qdrant_client is None:
            from qdrant_client import QdrantClient
            qdrant_client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        self.qdrant_client = qdrant_client

        self._injected_embed_model = embed_model
        if embed_model is None:
            # Preserve the production eager-loading behavior when no collaborator
            # is supplied explicitly.
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
        model = self._injected_embed_model or self._get_embed_model()
        embedding = await loop.run_in_executor(None, lambda: model.encode(query_text).tolist())
        
        def _search():
            if hasattr(self.qdrant_client, "query_points"):
                res = self.qdrant_client.query_points(
                    collection_name=collection,
                    query=embedding,
                    limit=limit
                )
                return [p.payload for p in res.points]
            elif hasattr(self.qdrant_client, "search"):
                res = self.qdrant_client.search(
                    collection_name=collection,
                    query_vector=embedding,
                    limit=limit
                )
                return [p.payload for p in res]
            else:
                raise AttributeError("QdrantClient has neither 'query_points' nor 'search' attribute!")
                
        return await loop.run_in_executor(None, _search)

    async def query_supabase(
        self,
        table: str,
        select: str = "*",
        filters: dict = None,
        limit: int = 10
    ) -> list:
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

    async def get_recent_sentiment(
        self,
        hours: int = None,
        asset_class: str = None
    ) -> dict:
        """Queries cloud Supabase news_articles via REST API for recent scored articles
        and classifies the *data status* so callers can tell genuinely-missing sentiment
        from a true-neutral read.

        Returns a dict containing:
            avg_score        float when status == OK, else None (so 0.0 can no longer
                             masquerade as "missing")
            sentiment_status one of sentiment_status.{OK, NO_DATA, ERROR, STALE}
            status_reason    human-readable explanation of the status
            label            "bullish" / "bearish" / "neutral"
            top_headlines    list[str]
            article_count    number of usable scored articles in the window
            raw_count        number of articles in the window regardless of scoring
                             (used to tell a broken scorer from a quiet news period)
            newest_age_min   age in minutes of the newest scored article (or None)

        Status semantics (see agents/sentiment_status.py):
            OK      = scored articles exist and the newest is within the staleness window
            STALE   = scored articles exist but the newest is older than the staleness window
            NO_DATA = query succeeded but zero usable scored articles (system failure)
            ERROR   = the query itself raised
        """
        from agents import sentiment_status as ss

        if hours is None:
            hours = ss.FRESHNESS_HOURS

        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=hours)).isoformat()

        base_filters = {}
        if asset_class:
            base_filters["asset_class"] = f"eq.{asset_class}"

        def _result(status, reason, avg=None, label="neutral", headlines=None,
                    article_count=0, raw_count=0, newest_age_min=None, extra=None):
            out = {
                "avg_score": avg,
                "sentiment_status": status,
                "status_reason": reason,
                "label": label,
                "top_headlines": headlines or [],
                "article_count": article_count,
                "raw_count": raw_count,
                "newest_age_min": newest_age_min,
            }
            if extra:
                out.update(extra)
            return out

        # ── Query 1: scored articles within the freshness window ──────────────
        scored_filters = dict(base_filters)
        scored_filters.update({
            "created_at": f"gt.{cutoff}",
            "sentiment_score": "not.is.null",
            "order": "created_at.desc",
        })
        try:
            rows = await self.query_supabase(
                table="news_articles",
                select="title,sentiment_score,created_at",
                filters=scored_filters,
                limit=100,
            )
        except Exception as e:
            logger.error(f"Error querying sentiment from Supabase: {e}")
            return _result(ss.ERROR, f"sentiment query failed: {e}")

        scores = [float(r["sentiment_score"]) for r in rows if r.get("sentiment_score") is not None] if rows else []

        if not scores:
            # No usable scored articles. Disambiguate a real failure from a quiet
            # (but healthy) news period using the raw collector output in the same
            # window: a quiet period still leaves older scored articles in-window
            # (which would surface as STALE above, never here), so reaching this
            # branch means the scorer/collector is not producing usable data.
            raw_filters = dict(base_filters)
            raw_filters["created_at"] = f"gt.{cutoff}"
            try:
                raw_rows = await self.query_supabase(
                    table="news_articles",
                    select="created_at",
                    filters=raw_filters,
                    limit=1,
                )
                raw_count = len(raw_rows)
            except Exception as e:
                logger.error(f"Error querying raw article count: {e}")
                return _result(ss.ERROR, f"raw-count query failed: {e}")

            if raw_count > 0:
                reason = ("collector producing articles but none are scored "
                          f"(scoring failure) in last {hours}h")
            else:
                reason = (f"zero articles in last {hours}h window "
                          "(collector/query failure)")
            logger.warning(f"[Sentiment] NO_DATA for asset_class={asset_class}: {reason}")
            return _result(ss.NO_DATA, reason, raw_count=raw_count)

        # ── We have usable scores: compute staleness from the newest article ──
        newest_age_min = None
        try:
            newest_ts = rows[0].get("created_at")
            if newest_ts:
                newest_dt = datetime.fromisoformat(str(newest_ts).replace("Z", "+00:00"))
                newest_age_min = round((now - newest_dt).total_seconds() / 60.0, 1)
        except Exception as e:
            logger.warning(f"[Sentiment] Could not parse newest article timestamp: {e}")

        avg_score = sum(scores) / len(scores)
        if avg_score > 0.2:
            label = "bullish"
        elif avg_score < -0.2:
            label = "bearish"
        else:
            label = "neutral"
        top_headlines = [r["title"] for r in rows if r.get("title")][:5]

        if newest_age_min is not None and newest_age_min > ss.STALENESS_MIN:
            # Data exists but is older than the staleness window → DEGRADE (not block).
            # avg is None (not OK); retain the computed value separately for visibility.
            reason = (f"newest scored article {newest_age_min:.0f}m old "
                      f"(> {ss.STALENESS_MIN}m staleness window)")
            return _result(
                ss.STALE, reason, avg=None, label=label, headlines=top_headlines,
                article_count=len(scores), raw_count=len(rows),
                newest_age_min=newest_age_min,
                extra={"stale_avg_score": round(avg_score, 6)},
            )

        return _result(
            ss.OK, "ok", avg=avg_score, label=label, headlines=top_headlines,
            article_count=len(scores), raw_count=len(rows),
            newest_age_min=newest_age_min,
        )

    @abc.abstractmethod
    async def analyze(self):
        """Abstract method to be implemented by subclassing agents."""
        pass
