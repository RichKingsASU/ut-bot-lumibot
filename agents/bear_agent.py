"""
BearAgent — Disrupting Alpha v2 debate layer.

Makes the strongest possible case AGAINST a trade. Uses Claude when an
ANTHROPIC_API_KEY is configured, otherwise falls back to a deterministic
rule-based bear score so the pipeline always produces a result.
"""

import logging

from agents.base_agent import BaseAgent
from agents._llm import call_claude, llm_available

logger = logging.getLogger("BearAgent")

_BEARISH_REGIMES = {"BEAR", "VOLATILE"}

_SYSTEM_PROMPT = (
    "You are a bear-case analyst. Given market data, make the strongest "
    "possible argument AGAINST entering this trade. Identify risks and red "
    "flags. Max 3 sentences."
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


class BearAgent(BaseAgent):
    """Builds the bear case for a candidate trade."""

    def __init__(self, name="BearAgent", qdrant_host="localhost", qdrant_port=6333):
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
        sym_regime_dict = regime_summary.get('symbol_regimes', {}).get(symbol, {})
        regime = sym_regime_dict.get('regime') or regime_summary.get('overall_regime', '')

        from agents.pead_signal import get_pead_signal
        pead = get_pead_signal(symbol)
        pead_context = f"Post-Earnings Signal: {pead.get('signal')}\n{pead.get('description')}"

        score = 0.0
        risks = []

        # 1. SENTIMENT (0-30 points bear case):
        sentiment = market_context.get('avg_sentiment', 0.0)
        if sentiment is None:
            sentiment = 0.0

        asset_class = (market_context or {}).get('asset_class') or (signal_recommendation or {}).get('asset_class') or 'equities'
        if asset_class == 'equities':
            base_bear = 50.0
            if regime == 'BEAR':
                base_bear += 15.0
            elif regime == 'VOLATILE':
                base_bear += 10.0
            
            sentiment_velocity = market_context.get('sentiment_velocity', 0.0)
            if sentiment_velocity < -0.05:
                base_bear += 8.0
                
            timesfm_forecast = signal_recommendation.get('timesfm_forecast', 'NONE')
            if timesfm_forecast == 'DOWN':
                base_bear += 7.0
                
            score = max(0.0, min(100.0, base_bear))
            risks.append(f"Equities rule-based scoring: base=50, regime={regime}, vel={sentiment_velocity:.3f}, linear_baseline={timesfm_forecast}")
        else:
            if sentiment < -0.3:
                score += 30
                risks.append(f'Strong bearish sentiment {sentiment:.2f}')
            elif sentiment < -0.1:
                score += 20
                risks.append(f'Mild bearish sentiment {sentiment:.2f}')
            elif sentiment < 0.1:
                score += 15
                risks.append(f'Neutral — no bullish catalyst {sentiment:.2f}')
            elif sentiment < 0.3:
                score += 5
                risks.append(f'Mild bullish sentiment {sentiment:.2f}')
            else:
                score += 0
                risks.append(f'Strong bullish sentiment {sentiment:.2f}')

            # 2. REGIME (0-30 points bear case):
            if regime == 'BEAR':
                score += 30
                risks.append('BEAR regime — strong headwind')
            elif regime == 'VOLATILE':
                score += 20
                risks.append('VOLATILE — downside risk elevated')
            elif regime == 'QUIET':
                score += 10
                risks.append('QUIET — limited upside momentum')
            elif regime == 'BULL':
                score += 5
                risks.append('BULL regime — bears fighting trend')
            else:
                score += 15
                risks.append('Unknown regime — uncertainty')

            # 3. TECHNICAL SIGNAL (0-20 points bear case):
            action = signal_recommendation.get('action', 'HOLD')
            sell_sig = signal_recommendation.get('sell_sig', False)
            buy_sig = signal_recommendation.get('buy_sig', False)
            if sell_sig or action == 'SELL':
                score += 20
                risks.append('Active SELL signal')
            elif action == 'HOLD' and not buy_sig:
                score += 10
                risks.append('No buy signal — momentum absent')
            elif buy_sig or action == 'BUY':
                score += 0
                risks.append('Active BUY signal — bull has edge')

            # 4. VELOCITY (0-10 points bear case):
            trend = market_context.get('sentiment_trend', 'STABLE')
            if trend == 'DETERIORATING':
                score += 10
                risks.append('Sentiment deteriorating')
            elif trend == 'STABLE':
                score += 5
                risks.append('No sentiment improvement')
            else:
                score += 0
                risks.append('Sentiment improving')

            # 5. GREEKS RISK (0-10 points bear case):
            if greeks_context:
                gamma = greeks_context.get('gamma', 0.0)
                rvol = greeks_context.get('rvol', 1.0)
                if gamma > 0.05:
                    score += 10
                    risks.append(f'High gamma {gamma:.4f} — risk elevated')
                elif rvol < 2.5:
                    score += 8
                    risks.append(f'Low RVOL {rvol:.1f}x — thin volume')
                else:
                    score += 2
                    risks.append('Greeks within normal range')

            score = min(100.0, score)

        if pead['signal'] == 'BEARISH_DRIFT':
            score -= pead.get('modifier', 0)
            risks.append(f"PEAD bearish drift modifier: +{abs(pead.get('modifier', 0))}")
        score = max(0.0, min(100.0, score))

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
            
        # Use passed in-memory regime_summary
        sym_regime_dict = regime_summary.get('symbol_regimes', {}).get(symbol, {})
        sym_regime = sym_regime_dict.get('regime') or regime_summary.get('overall_regime', 'Unknown')
        sym_prob = sym_regime_dict.get('regime_probability')
        if sym_prob is not None:
            regime_str = f"{sym_regime} (Prob: {sym_prob})"
        else:
            regime_str = f"{sym_regime}"
            
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
        sentiment_str = "\n".join([f"  - {ns.get('title')} (score: {ns.get('sentiment_score')})" for ns in recent_sentiment]) if recent_sentiment else "  None"

        from agents._llm import call_claude, llm_available
        reasoning = ' | '.join(risks)

        gex_context = market_context.get('gex_context', 'N/A')
        ma_context = market_context.get('ma_context', 'N/A')

        if llm_available():
            regime_val_str = f"{sym_regime} ({sym_prob:.0%})" if sym_prob is not None else f"{sym_regime}"
            prompt = f'''
Symbol: {symbol}
Regime: {regime_val_str}
Sentiment: {sentiment:.3f} [status: {market_context.get("sentiment_status", "OK")}]
Velocity: {market_context.get("sentiment_trend", "STABLE")}
Signal: {signal_recommendation.get("action", "HOLD")}
Bear score: {score:.0f}/100

Dealer Gamma Positioning:
{gex_context}

200-day MA Regime:
{ma_context}

Post-Earnings Signal:
{pead_context}

Live Signals (Supabase):
{signals_str}

Live News Sentiment (Supabase):
{sentiment_str}

In exactly 2 sentences, make the strongest case AGAINST entering a long position on {symbol} right now. Identify the key risks.
At the very end, output: "Score: <number>" where <number> is your final bear score between 0 and 100 based on the analysis.
'''
            llm_text = await call_claude(
                system='You are a bear-case risk analyst. Be concise, specific, data-driven.',
                user=prompt,
                max_tokens=150
            )
            if llm_text:
                reasoning = llm_text
                logger.info(f'[Bear] LLM reasoning: {llm_text[:60]}')
                import re
                match = re.search(r"Score:\s*(\d+)", llm_text, re.IGNORECASE)
                if match:
                    score = float(match.group(1))
                    logger.info(f'[Bear] Extracted score from LLM: {score}')

        confidence = ('HIGH' if score >= 70
                      else 'MEDIUM' if score >= 40
                      else 'LOW')

        return {
            'agent': 'bear',
            'symbol': symbol,
            'score': round(score, 1),
            'reasoning': reasoning,
            'key_risks': risks,
            'confidence': confidence
        }

    @staticmethod
    def _format_context(
        symbol, sentiment, regime, signal_type, sell_sig,
        iv_rank, rvol, gamma, delta, headlines,
    ) -> str:
        headline_block = "\n".join(f"  - {h}" for h in headlines[:5]) or "  (none)"
        return (
            f"Symbol: {symbol}\n"
            f"Sentiment score: {sentiment:.2f} (<-0.2 is bearish)\n"
            f"Market regime: {regime}\n"
            f"Technical signal: {signal_type} (sell signal active: {sell_sig})\n"
            f"IV rank: {iv_rank:.0f} (>70 means expensive options)\n"
            f"Relative volume (RVOL): {rvol:.1f}x (<1.0 means no institutional interest)\n"
            f"Gamma: {gamma:.4f} (>0.05 is elevated gamma risk)\n"
            f"Delta exposure: {delta:.2f}\n"
            f"Recent headlines:\n{headline_block}\n\n"
            f"Make the strongest data-driven case AGAINST entering this trade."
        )
