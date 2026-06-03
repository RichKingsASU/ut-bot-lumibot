"""
BullAgent — Disrupting Alpha v2 debate layer.

Makes the strongest possible case FOR a trade. Uses Claude when an
ANTHROPIC_API_KEY is configured, otherwise falls back to a deterministic
rule-based bull score so the pipeline always produces a result.
"""

import logging

from agents.base_agent import BaseAgent
from agents._llm import call_claude, llm_available

logger = logging.getLogger("BullAgent")

_BULLISH_REGIMES = {"BULL"}

_SYSTEM_PROMPT = (
    "You are a bull-case analyst. Given market data, make the strongest "
    "possible argument FOR entering this trade. Be specific and data-driven. "
    "Max 3 sentences."
)


def _truthy(value) -> bool:
    """Normalise bool/int/string truthy representations from mixed sources."""
    if isinstance(value, bool):
        return value
    return value in (1, "1", "true", "True", "TRUE", "t")


def _confidence_from_score(score: float) -> str:
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


class BullAgent(BaseAgent):
    """Builds the bull case for a candidate trade."""

    def __init__(self, name="BullAgent", qdrant_host="localhost", qdrant_port=6333):
        super().__init__(name, qdrant_host, qdrant_port)

    async def analyze(
        self,
        symbol: str,
        market_context: dict,
        signal_recommendation: dict,
        greeks_context: dict = None,
        regime_summary: dict = None,
    ) -> dict:
        market_context = market_context or {}
        signal_recommendation = signal_recommendation or {}
        greeks_context = greeks_context or {}
        regime_summary = regime_summary or {}

        score = 0.0
        factors = []

        # 1. SENTIMENT (0-30 points):
        sentiment = market_context.get('avg_sentiment', 0.0)
        if sentiment is None:
            sentiment = 0.0

        asset_class = (market_context or {}).get('asset_class') or (signal_recommendation or {}).get('asset_class') or 'equities'
        if asset_class == 'equities':
            base_bull = 50.0
            regime = (regime_summary or {}).get('overall_regime', '')
            if regime == 'BULL':
                base_bull += 15.0
            
            sentiment_velocity = market_context.get('sentiment_velocity', 0.0)
            if sentiment_velocity > 0.05:
                base_bull += 8.0
                
            timesfm_forecast = signal_recommendation.get('timesfm_forecast', 'NONE')
            if timesfm_forecast == 'UP':
                base_bull += 7.0
                
            score = max(0.0, min(100.0, base_bull))
            factors.append(f"Equities rule-based scoring: base=50, regime={regime}, vel={sentiment_velocity:.3f}, timesfm={timesfm_forecast}")
        else:
            if sentiment > 0.3:
                score += 30
                factors.append(f'Strong bullish sentiment {sentiment:.2f}')
            elif sentiment > 0.1:
                score += 20
                factors.append(f'Mild bullish sentiment {sentiment:.2f}')
            elif sentiment > -0.1:
                score += 10
                factors.append(f'Neutral sentiment {sentiment:.2f}')
            elif sentiment > -0.3:
                score += 5
                factors.append(f'Mild bearish sentiment {sentiment:.2f}')
            else:
                score += 0
                factors.append(f'Strong bearish sentiment {sentiment:.2f}')

            # 2. REGIME (0-30 points):
            regime = (regime_summary or {}).get('overall_regime', '')
            if regime == 'BULL':
                score += 30
                factors.append('BULL regime — strong tailwind')
            elif regime == 'QUIET':
                score += 20
                factors.append('QUIET regime — mean reversion opportunity')
            elif regime == 'VOLATILE':
                score += 15
                factors.append('VOLATILE — explosive move possible')
            elif regime == 'BEAR':
                score += 5
                factors.append('BEAR regime — headwind')
            else:
                score += 10
                factors.append('Unknown regime')

            # 3. TECHNICAL SIGNAL (0-20 points):
            action = signal_recommendation.get('action', 'HOLD')
            buy_sig = signal_recommendation.get('buy_sig', False)
            sell_sig = signal_recommendation.get('sell_sig', False)
            if buy_sig or action == 'BUY':
                score += 20
                factors.append('Active BUY signal')
            elif action == 'HOLD' and not sell_sig:
                score += 10
                factors.append('Neutral signal — no active sell')
            elif sell_sig or action == 'SELL':
                score += 0
                factors.append('Active SELL signal — bearish')

            # 4. SENTIMENT VELOCITY (0-10 points):
            velocity = market_context.get('sentiment_velocity', 0.0)
            trend = market_context.get('sentiment_trend', 'STABLE')
            if trend == 'IMPROVING':
                score += 10
                factors.append('Sentiment improving')
            elif trend == 'STABLE':
                score += 5
                factors.append('Sentiment stable')
            else:
                score += 0
                factors.append('Sentiment deteriorating')

            # 5. GREEKS MODE (0-10 points):
            if greeks_context:
                trade_mode = greeks_context.get('trade_mode', 'NEUTRAL')
                iv_rank = greeks_context.get('iv_rank', 50.0)
                if trade_mode == 'LONG_GAMMA':
                    score += 10
                    factors.append('LONG_GAMMA — IV cheap')
                elif trade_mode == 'NEUTRAL':
                    score += 5
                    factors.append('Greeks neutral')
                else:
                    score += 2
                    factors.append('SHORT_PREMIUM mode')

            score = min(100.0, score)

        # Fetch live data from Supabase
        asset_class = (market_context or {}).get('asset_class') or (signal_recommendation or {}).get('asset_class') or 'equities'
        asset_filter = "eq.crypto" if asset_class == "crypto" else "in.(equity,equities)"
        
        latest_signals = []
        current_regime_row = None
        recent_sentiment = []
        
        try:
            latest_signals = await self.query_supabase(
                table="agent_signals",
                select="symbol,action,confidence,created_at",
                filters={"symbol": f"eq.{symbol}", "order": "created_at.desc"},
                limit=5
            )
        except Exception as e:
            logger.error(f"Failed to query live agent_signals from Supabase: {e}")
            
        try:
            regime_rows = await self.query_supabase(
                table="regime_states",
                select="regime,regime_probability,detected_at",
                filters={"symbol": f"eq.{symbol}", "order": "detected_at.desc"},
                limit=1
            )
            if regime_rows:
                current_regime_row = regime_rows[0]
        except Exception as e:
            logger.error(f"Failed to query live regime_states from Supabase: {e}")
            
        try:
            recent_sentiment = await self.query_supabase(
                table="news_articles",
                select="title,sentiment_score,created_at",
                filters={"asset_class": f"eq.{asset_class}", "sentiment_score": "not.is.null", "order": "created_at.desc"},
                limit=5
            )
        except Exception as e:
            logger.error(f"Failed to query live news sentiment from Supabase: {e}")

        signals_str = "\n".join([f"  - {s.get('symbol')}: {s.get('action')} ({s.get('confidence')})" for s in latest_signals]) if latest_signals else "  None"
        regime_str = f"{current_regime_row.get('regime')} (Prob: {current_regime_row.get('regime_probability')})" if current_regime_row else "Unknown"
        sentiment_str = "\n".join([f"  - {ns.get('title')} (score: {ns.get('sentiment_score')})" for ns in recent_sentiment]) if recent_sentiment else "  None"

        from agents._llm import call_claude, llm_available
        reasoning = ' | '.join(factors)

        if llm_available():
            prompt = f'''
Symbol: {symbol}
Regime: {regime_summary.get("overall_regime") if regime_summary else "Unknown"} (Live Regime: {regime_str})
Sentiment: {sentiment:.3f} ({market_context.get("sentiment_label", "neutral")}) [status: {market_context.get("sentiment_status", "OK")}]
Velocity: {market_context.get("sentiment_trend", "STABLE")}
Signal: {signal_recommendation.get("action", "HOLD")}
Bull score: {score:.0f}/100

Live Signals (Supabase):
{signals_str}

Live News Sentiment (Supabase):
{sentiment_str}

In exactly 2 sentences, make the strongest case FOR entering a long position on {symbol} right now. Be specific about the data above.
At the very end, output: "Score: <number>" where <number> is your final bull score between 0 and 100 based on the analysis.
'''
            llm_text = await call_claude(
                system='You are a bull-case trading analyst. Be concise, specific, data-driven.',
                user=prompt,
                max_tokens=150
            )
            if llm_text:
                reasoning = llm_text
                logger.info(f'[Bull] LLM reasoning: {llm_text[:60]}')
                import re
                match = re.search(r"Score:\s*(\d+)", llm_text, re.IGNORECASE)
                if match:
                    score = float(match.group(1))
                    logger.info(f'[Bull] Extracted score from LLM: {score}')

        confidence = ('HIGH' if score >= 70
                      else 'MEDIUM' if score >= 40
                      else 'LOW')

        return {
            'agent': 'bull',
            'symbol': symbol,
            'score': round(score, 1),
            'reasoning': reasoning,
            'key_factors': factors,
            'confidence': confidence
        }

    @staticmethod
    def _format_context(
        symbol, sentiment, regime, signal_type, buy_sig, iv_rank, rvol, headlines,
    ) -> str:
        headline_block = "\n".join(f"  - {h}" for h in headlines[:5]) or "  (none)"
        return (
            f"Symbol: {symbol}\n"
            f"Sentiment score: {sentiment:.2f} (>0.2 is bullish)\n"
            f"Market regime: {regime}\n"
            f"Technical signal: {signal_type} (buy signal active: {buy_sig})\n"
            f"IV rank: {iv_rank:.0f} (<30 means cheap options)\n"
            f"Relative volume (RVOL): {rvol:.1f}x (>2.5 means institutional interest)\n"
            f"Recent headlines:\n{headline_block}\n\n"
            f"Make the strongest data-driven case FOR going long/entering this trade."
        )
