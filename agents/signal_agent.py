import asyncio
import json
import logging
import os
import httpx
from datetime import datetime, timezone
from agents.base_agent import BaseAgent

logger = logging.getLogger("SignalAgent")


class SignalAgent(BaseAgent):
    def __init__(self, name="SignalAgent", asset_class="crypto", qdrant_host="localhost", qdrant_port=6333, nats_url=None):
        super().__init__(name, qdrant_host, qdrant_port)
        self.asset_class = asset_class

        is_docker = os.path.exists("/.dockerenv")
        default_nats = "nats://nats:4222" if is_docker else "nats://localhost:4222"
        self.nats_url = nats_url or os.getenv("NATS_URL") or default_nats

    async def analyze(self, market_context: dict) -> dict:
        """Analyze market context and return a signal_recommendation dict.

        Args:
            market_context: dict produced by MarketAnalystAgent.analyze(), expected to contain:
                - avg_sentiment: float
                - recent_signals: list of signal_log rows
                - ... other fields

        Returns:
            {
                action: "BUY"|"SELL"|"HOLD",
                confidence: "HIGH"|"MEDIUM"|"LOW",
                sentiment_score: float,
                technical_signal: str,
                reasoning: str
            }
        """
        logger.info("SignalAgent.analyze() started.")

        # ── Step 1: Get last 5 rows from signal_log via query_supabase ────────
        try:
            filters = {}
            if self.asset_class == "crypto":
                filters["symbol"] = "like.%USD%"
            elif self.asset_class == "equities":
                filters["symbol"] = "in.(SPY,IWM,QQQ)"
            signal_rows = await self.query_supabase(
                table="signal_log",
                select="*",
                filters=filters,
                limit=5
            )
        except Exception as e:
            logger.error(f"Error querying signal_log: {e}")
            signal_rows = []

        # ── Step 2: Extract latest signal_type and buy_sig/sell_sig ───────────
        latest_signal_type = "NONE"
        buy_sig = False
        sell_sig = False

        if signal_rows:
            latest = signal_rows[0]
            latest_signal_type = str(latest.get("signal_type", "NONE")).upper()
            raw_buy = latest.get("buy_sig", False)
            raw_sell = latest.get("sell_sig", False)
            # Handle various truthy representations (bool / int / string)
            buy_sig = raw_buy in (True, 1, "true", "True", "1") if not isinstance(raw_buy, bool) else raw_buy
            sell_sig = raw_sell in (True, 1, "true", "True", "1") if not isinstance(raw_sell, bool) else raw_sell

        logger.info(
            f"Latest signal → type={latest_signal_type}, buy_sig={buy_sig}, sell_sig={sell_sig}"
        )

        # ── Step 3: Combine with market_context.avg_sentiment ─────────────────
        avg_sentiment: float = float(market_context.get("avg_sentiment", 0.0))

        if avg_sentiment > 0.3 and buy_sig:
            action = "BUY"
            confidence = "HIGH"
            reasoning = (
                f"Bullish sentiment ({avg_sentiment:.3f} > 0.3) confirmed by buy signal "
                f"from signal_log (signal_type={latest_signal_type})."
            )
        elif avg_sentiment < -0.3 and sell_sig:
            action = "SELL"
            confidence = "HIGH"
            reasoning = (
                f"Bearish sentiment ({avg_sentiment:.3f} < -0.3) confirmed by sell signal "
                f"from signal_log (signal_type={latest_signal_type})."
            )
        elif (avg_sentiment > 0.3 and sell_sig) or (avg_sentiment < -0.3 and buy_sig):
            # Sentiment conflicts with technical signal
            action = "HOLD"
            confidence = "LOW"
            reasoning = (
                f"Sentiment ({avg_sentiment:.3f}) conflicts with technical signal "
                f"(buy_sig={buy_sig}, sell_sig={sell_sig}). Holding to avoid conflicting signals."
            )
        else:
            # Medium confidence — follow the technical signal
            if buy_sig:
                action = "BUY"
            elif sell_sig:
                action = "SELL"
            else:
                action = "HOLD"
            confidence = "MEDIUM"
            reasoning = (
                f"Neutral sentiment region ({avg_sentiment:.3f}). Following technical signal: "
                f"signal_type={latest_signal_type}, buy_sig={buy_sig}, sell_sig={sell_sig}."
            )

        signal_recommendation = {
            "asset_class": self.asset_class,
            "action": action,
            "confidence": confidence,
            "sentiment_score": avg_sentiment,
            "technical_signal": latest_signal_type,
            "reasoning": reasoning,
        }

        logger.info(f"Signal recommendation → {signal_recommendation}")

        # ── Step 4: Publish to NATS agents.signal_recommendation ──────────────
        try:
            import nats
            nc = await nats.connect(self.nats_url)
            await nc.publish(
                "agents.signal_recommendation",
                json.dumps(signal_recommendation).encode("utf-8")
            )
            await nc.close()
            logger.info("Published signal_recommendation to NATS 'agents.signal_recommendation'.")
        except Exception as e:
            logger.error(f"Failed to publish signal_recommendation to NATS: {e}")

        # ── Step 5: Write to cloud Supabase agent_signals table via REST API ──
        try:
            if self.supabase_url and self.supabase_anon_key:
                url = f"{self.supabase_url}/rest/v1/agent_signals"
                headers = {
                    "apikey": self.supabase_anon_key,
                    "Authorization": f"Bearer {self.supabase_anon_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                }
                payload = {
                    **signal_recommendation,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "agent_name": self.name,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code in (200, 201):
                        logger.info("signal_recommendation written to Supabase agent_signals.")
                    else:
                        logger.error(
                            f"Supabase insert failed: {resp.status_code} — {resp.text}"
                        )
            else:
                logger.warning("Supabase credentials not set; skipping agent_signals write.")
        except Exception as e:
            logger.error(f"Failed to write signal_recommendation to Supabase: {e}")

        return signal_recommendation
