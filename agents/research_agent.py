"""
ResearchAgent — Disrupting Alpha v2 Phase 4
Produces an overnight digest: regime, sentiment, top headlines, similar past periods.
Sends digest via Telegram and upserts to Qdrant agent_memory.
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

from agents.base_agent import BaseAgent

logger = logging.getLogger("ResearchAgent")

load_dotenv()
_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8641189809")


async def _send_telegram(text: str, chat_id: str = _TELEGRAM_CHAT_ID) -> None:
    """Send a Telegram message via the Bot API (best-effort, never raises)."""
    token = _TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram message sent successfully.")
            else:
                logger.error(f"Telegram send failed: {resp.status_code} — {resp.text}")
    except Exception as exc:
        logger.error(f"Telegram send exception: {exc}")


class ResearchAgent(BaseAgent):
    """Overnight research digest agent."""

    def __init__(self, name: str = "ResearchAgent", asset_class: str = "crypto", qdrant_host: str = "localhost", qdrant_port: int = 6333):
        super().__init__(name, qdrant_host, qdrant_port)
        self.asset_class = asset_class

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    async def analyze(self) -> dict:
        """Produce and distribute the overnight research digest.

        Returns
        -------
        dict with keys:
            regime, avg_sentiment_24h, top_positive_headlines,
            top_negative_headlines, article_count, similar_past_periods,
            digest_timestamp
        """
        logger.info("ResearchAgent.analyze() started.")

        # ── Step 1: Query news_articles last 24 h with sentiment scores ────────
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        filters = {
            "created_at": f"gt.{cutoff}",
            "sentiment_score": "not.is.null",
            "order": "created_at.desc",
        }
        if self.asset_class:
            filters["asset_class"] = f"eq.{self.asset_class}"

        try:
            rows = await self.query_supabase(
                table="news_articles",
                select="title,sentiment_score",
                filters=filters,
                limit=200,
            )
        except Exception as exc:
            logger.error(f"Supabase query error: {exc}")
            rows = []

        # ── Step 2: Calculate avg sentiment and detect regime ──────────────────
        scores = [float(r["sentiment_score"]) for r in rows if r.get("sentiment_score") is not None]
        article_count = len(scores)

        if scores:
            avg_sentiment_24h = round(sum(scores) / len(scores), 6)
        else:
            avg_sentiment_24h = 0.0

        if avg_sentiment_24h > 0.2:
            regime = "BULL"
        elif avg_sentiment_24h < -0.2:
            regime = "BEAR"
        else:
            regime = "NEUTRAL"

        logger.info(f"Regime={regime}, avg_sentiment={avg_sentiment_24h:.4f}, articles={article_count}")

        # ── Step 3: Sort top 3 positive and top 3 negative headlines ──────────
        titled_rows = [r for r in rows if r.get("title") and r.get("sentiment_score") is not None]

        positive = sorted(
            [r for r in titled_rows if float(r["sentiment_score"]) > 0.3],
            key=lambda r: float(r["sentiment_score"]),
            reverse=True,
        )
        top_positive_headlines = [r["title"] for r in positive[:3]]

        negative = sorted(
            [r for r in titled_rows if float(r["sentiment_score"]) < -0.3],
            key=lambda r: float(r["sentiment_score"]),
        )
        top_negative_headlines = [r["title"] for r in negative[:3]]

        # ── Step 4: Query Qdrant agent_memory for similar past regimes ─────────
        similar_past_periods: list[dict] = []
        try:
            query_text = f"overnight regime {regime} sentiment {avg_sentiment_24h:.4f}"
            results = await self.query_qdrant(
                query_text=query_text,
                collection="agent_memory",
                limit=5,
            )
            for payload in results:
                if isinstance(payload, dict) and payload.get("key") == "overnight_digest":
                    similar_past_periods.append(payload)
        except Exception as exc:
            logger.error(f"Qdrant query error: {exc}")

        # ── Step 5: Compose digest ─────────────────────────────────────────────
        digest_timestamp = datetime.now(timezone.utc).isoformat()
        overnight_digest = {
            "asset_class": self.asset_class,
            "regime": regime,
            "avg_sentiment_24h": avg_sentiment_24h,
            "top_positive_headlines": top_positive_headlines,
            "top_negative_headlines": top_negative_headlines,
            "article_count": article_count,
            "similar_past_periods": similar_past_periods,
            "digest_timestamp": digest_timestamp,
        }

        # ── Step 6: Send via Telegram ──────────────────────────────────────────
        title = "📊 Crypto Market Digest" if self.asset_class == "crypto" else "📊 Equities Market Digest"
        pos_block = "\n".join(f"  • {h}" for h in top_positive_headlines) if top_positive_headlines else "  (none)"
        neg_block = "\n".join(f"  • {h}" for h in top_negative_headlines) if top_negative_headlines else "  (none)"
        tg_message = (
            f"🌙 <b>{title}</b>\n"
            f"📅 {digest_timestamp}\n\n"
            f"📊 Regime: <b>{regime}</b>\n"
            f"📈 Avg Sentiment (24h): <b>{avg_sentiment_24h:.4f}</b>\n"
            f"📰 Articles Analysed: <b>{article_count}</b>\n\n"
            f"✅ <b>Top Positive Headlines:</b>\n{pos_block}\n\n"
            f"❌ <b>Top Negative Headlines:</b>\n{neg_block}\n\n"
            f"🔍 Similar Past Periods Found: <b>{len(similar_past_periods)}</b>"
        )
        await _send_telegram(tg_message, chat_id="8641189809")

        # ── Step 7: Upsert digest to Qdrant agent_memory ──────────────────────
        try:
            loop = asyncio.get_running_loop()
            embed_text = f"overnight_digest regime={regime} sentiment={avg_sentiment_24h:.4f}"
            embedding = await loop.run_in_executor(
                None, lambda: self._get_embed_model().encode(embed_text).tolist()
            )

            key_hash = hashlib.md5(f"overnight_digest_{digest_timestamp}".encode()).hexdigest()
            point_id = int(key_hash[:16], 16)

            payload = {
                "key": "overnight_digest",
                "overnight_digest": overnight_digest,
                "updated_at": digest_timestamp,
            }

            await loop.run_in_executor(
                None,
                lambda: self.qdrant_client.upsert(
                    collection_name="agent_memory",
                    points=[
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": payload,
                        }
                    ],
                ),
            )
            logger.info("Upserted overnight_digest to Qdrant agent_memory.")
        except Exception as exc:
            logger.error(f"Qdrant upsert error: {exc}")

        # ── Step 8: Return digest ──────────────────────────────────────────────
        return overnight_digest
