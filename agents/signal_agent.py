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

    async def analyze(self, market_context: dict, greeks_context: dict = None) -> dict:
        """Analyze market context and return a signal_recommendation dict.

        Args:
            market_context: dict produced by MarketAnalystAgent.analyze(), expected to contain:
                - avg_sentiment: float
                - recent_signals: list of signal_log rows
                - ... other fields
            greeks_context: optional dict from greeks_decision (greeks_intercept node).
                When provided, modifies confidence based on IV Rank / trade mode alignment.

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

        # ── Step 3: Combine with market_context sentiment (status-aware) ──────
        # avg_sentiment is only trustworthy when sentiment_status == OK. For every
        # other state it is None, so a 0.0 can no longer masquerade as a real
        # neutral read. Policy:
        #   NO_DATA / ERROR -> HOLD/BLOCK  (do not trade on missing/failed sentiment)
        #                      unless this asset class is in degrade-only mode.
        #   STALE           -> DEGRADE     (follow technicals at reduced conviction).
        #   OK              -> normal sentiment-confirmed logic.
        from agents import sentiment_status as ss

        sentiment_status = str(market_context.get("sentiment_status", ss.OK))
        status_reason = str(
            market_context.get("status_reason")
            or market_context.get("sentiment_status_reason")
            or ""
        )
        raw_avg = market_context.get("avg_sentiment", None)
        avg_sentiment: float = (
            float(raw_avg) if (sentiment_status == ss.OK and raw_avg is not None) else 0.0
        )

        action = "HOLD"
        confidence = "MEDIUM"
        reasoning = ""
        sentiment_blocked = False  # True when we hard-blocked on missing/failed sentiment

        if sentiment_status in ss.MISSING_STATES and ss.enforces_block(self.asset_class):
            # HOLD/BLOCK: refuse to trade on missing/failed sentiment.
            sentiment_blocked = True
            action = "HOLD"
            confidence = "LOW"
            reasoning = (
                f"BLOCK: sentiment {sentiment_status} ({status_reason}). "
                f"Refusing to trade on missing/failed sentiment data."
            )
        elif sentiment_status == ss.OK:
            # Normal sentiment-confirmed logic.
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
                confidence = "MEDIUM"
                reasoning = (
                    f"Neutral sentiment region ({avg_sentiment:.3f}). Following technical signal: "
                    f"signal_type={latest_signal_type}, buy_sig={buy_sig}, sell_sig={sell_sig}."
                )
        else:
            # DEGRADE: STALE (any asset), or NO_DATA/ERROR where blocking is not
            # enforced (e.g. equities until the scorer scores equities). Do NOT use
            # the (missing/stale) sentiment value; follow the technical signal at
            # reduced conviction and flag it.
            if buy_sig and not sell_sig:
                action = "BUY"
            elif sell_sig and not buy_sig:
                action = "SELL"
            else:
                action = "HOLD"
            confidence = "LOW"
            reasoning = (
                f"DEGRADE: sentiment {sentiment_status} ({status_reason}). "
                f"Proceeding on technical signal only at reduced conviction "
                f"(signal_type={latest_signal_type}, buy_sig={buy_sig}, sell_sig={sell_sig})."
            )

        symbol = latest.get("symbol", "ETH/USD" if self.asset_class == "crypto" else "SPY") if signal_rows else ("ETH/USD" if self.asset_class == "crypto" else "SPY")

        try:
            from agents.macro_filter import MacroFilter
            mf = MacroFilter()
            macro_check = mf.should_trade(symbol)
            if not macro_check['approved']:
                action = 'HOLD'
                confidence = 'LOW'
                reasoning += f' | Macro filter: {macro_check["reason"]}'
        except Exception as e:
            logger.error(f"Macro filter failed: {e}")

        sentiment_velocity = 0.0
        sentiment_trend = "STABLE"
        try:
            from agents.sentiment_velocity import SentimentVelocity
            sv = SentimentVelocity()
            vel_result = await sv.calculate(self.asset_class)
            sentiment_velocity = vel_result['velocity']
            sentiment_trend = vel_result['trend']
            
            if sentiment_trend == 'IMPROVING' and action == 'BUY':
                if confidence == 'MEDIUM': confidence = 'HIGH'
            elif sentiment_trend == 'DETERIORATING' and action == 'BUY':
                if confidence == 'HIGH': confidence = 'MEDIUM'
        except Exception as e:
            logger.error(f"Sentiment velocity failed: {e}")
        
        try:
            from agents.timesfm_forecaster import TimesFMForecaster
            forecaster = TimesFMForecaster()
            forecast = forecaster.forecast(
                symbol=symbol,
                asset_class=self.asset_class
            )
            if forecast:
                modifier = forecaster.get_signal_modifier(
                    forecast, action
                )
                confidence_boost = modifier['confidence_boost']
                if confidence_boost > 0 and confidence == 'MEDIUM':
                    confidence = 'HIGH'
                elif confidence_boost < 0 and confidence == 'HIGH':
                    confidence = 'MEDIUM'
                reasoning += f" | TimesFM: {forecast['forecast_direction']} ({forecast['forecast_pct_change']:+.1f}%)"
                timesfm_forecast = forecast['forecast_direction']
                timesfm_pct = forecast['forecast_pct_change']
            else:
                timesfm_forecast = "NONE"
                timesfm_pct = 0.0
        except Exception as e:
            logger.warning(f'TimesFM integration skipped: {e}')
            timesfm_forecast = 0.0
            timesfm_pct = 0.0

        signal_recommendation = {
            "asset_class": self.asset_class,
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "sentiment_score": avg_sentiment,
            "sentiment_status": sentiment_status,
            "sentiment_status_reason": status_reason,
            "sentiment_blocked": sentiment_blocked,
            "sentiment_velocity": sentiment_velocity,
            "sentiment_trend": sentiment_trend,
            "technical_signal": latest_signal_type,
            "reasoning": reasoning,
            "timesfm_forecast": timesfm_forecast,
            "timesfm_pct": timesfm_pct,
        }

        # ── Step 3b: Greeks modifier ───────────────────────────────────────────
        if greeks_context and greeks_context.get('trade_mode'):
            trade_mode = greeks_context.get('trade_mode', 'NEUTRAL')
            iv_rank = greeks_context.get('iv_rank', 50.0)
            gamma = greeks_context.get('gamma', 0.0)

            # Boost confidence if Greeks align
            if trade_mode == 'LONG_GAMMA' and action == 'BUY':
                if confidence == 'MEDIUM':
                    confidence = 'HIGH'
                reasoning += f" | Greeks confirm: IV Rank {iv_rank:.0f} favors long gamma"

            elif trade_mode == 'SHORT_PREMIUM' and action == 'SELL':
                if confidence == 'MEDIUM':
                    confidence = 'HIGH'
                reasoning += f" | Greeks confirm: IV Rank {iv_rank:.0f} favors premium selling"

            elif trade_mode != 'NEUTRAL':
                if ((trade_mode == 'LONG_GAMMA' and action == 'SELL') or
                        (trade_mode == 'SHORT_PREMIUM' and action == 'BUY')):
                    if confidence == 'HIGH':
                        confidence = 'MEDIUM'
                    reasoning += f" | Greeks conflict: IV Rank {iv_rank:.0f} vs signal direction"

            signal_recommendation['trade_mode'] = trade_mode
            signal_recommendation['iv_rank'] = iv_rank
            signal_recommendation['gamma'] = gamma
            # Update confidence after possible modification
            signal_recommendation['confidence'] = confidence
            signal_recommendation['reasoning'] = reasoning

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
            service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
            if self.supabase_url and service_role_key:
                url = f"{self.supabase_url}/rest/v1/agent_signals"
                headers = {
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                }
                payload = {
                    "asset_class": signal_recommendation.get("asset_class"),
                    "symbol": signal_recommendation.get("symbol"),
                    "action": signal_recommendation.get("action"),
                    "confidence": signal_recommendation.get("confidence"),
                    "reasoning": signal_recommendation.get("reasoning"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "agent_name": self.name,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code in (200, 201):
                        logger.info("signal_recommendation written to Supabase agent_signals.")
                        resp_data = resp.json()
                        if resp_data and isinstance(resp_data, list):
                            inserted_id = resp_data[0].get("id")
                            if inserted_id:
                                signal_recommendation["id"] = inserted_id
                                logger.info(f"Stored agent_signal ID: {inserted_id} in recommendation.")
                    else:
                        logger.error(
                            f"Supabase insert failed: {resp.status_code} — {resp.text}"
                        )
            else:
                logger.warning("Supabase credentials not set; skipping agent_signals write.")
        except Exception as e:
            logger.error(f"Failed to write signal_recommendation to Supabase: {e}")

        return signal_recommendation
