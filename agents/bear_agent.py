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

        score = 0.0
        risks = []

        # 1. SENTIMENT (0-30 points bear case):
        sentiment = market_context.get('avg_sentiment', 0.0)
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
        regime = (regime_summary or {}).get('overall_regime', '')
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

        from agents._llm import call_claude, llm_available
        reasoning = ' | '.join(risks)

        if llm_available():
            prompt = f'''
Symbol: {symbol}
Regime: {regime_summary.get("overall_regime") if regime_summary else "Unknown"}
Sentiment: {market_context.get("avg_sentiment", 0):.3f}
Velocity: {market_context.get("sentiment_trend", "STABLE")}
Signal: {signal_recommendation.get("action", "HOLD")}
Bear score: {score:.0f}/100

In exactly 2 sentences, make the strongest
case AGAINST entering a long position on {symbol}
right now. Identify the key risks.
'''
            llm_text = await call_claude(
                system='You are a bear-case risk analyst. Be concise, specific, data-driven.',
                user=prompt,
                max_tokens=150
            )
            if llm_text:
                reasoning = llm_text
                logger.info(f'[Bear] LLM reasoning: {llm_text[:60]}')

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
