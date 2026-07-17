"""
JudgeAgent — Disrupting Alpha v2 debate layer.

Weighs the bull and bear cases and renders a final verdict. The net score
(bull - bear) deterministically sets the baseline verdict; when an
ANTHROPIC_API_KEY_AGENTS is configured, Claude synthesises the reasoning and may
sharpen confidence, but the proceed/avoid decision stays grounded in the
numeric net score.
"""

import json
import logging

from agents.base_agent import BaseAgent
from agents._llm import call_claude, llm_available

logger = logging.getLogger("JudgeAgent")

# Verdicts for which the trade is allowed to proceed.
_PROCEED_VERDICTS = {"PROCEED", "PROCEED_CAUTIOUSLY"}

# Recommended size as a fraction of normal position size, keyed by verdict.
_SIZE_FRACTION = {
    "PROCEED": 1.0,
    "PROCEED_CAUTIOUSLY": 0.5,
    "HOLD": 0.0,
    "AVOID": 0.0,
    "STRONG_AVOID": 0.0,
}

_SYSTEM_PROMPT = (
    "You are a trading judge. Given bull and bear arguments, synthesize a "
    "final verdict. Be decisive. Output JSON with: verdict, reasoning, "
    "confidence (0-100), key_insight (one sentence)."
)


def _verdict_from_net(net_score: float) -> tuple[str, str]:
    """Map net score → (verdict, confidence_modifier) per the spec thresholds."""
    if net_score > 30:
        return "PROCEED", "HIGH"
    if net_score > 10:
        return "PROCEED_CAUTIOUSLY", "MEDIUM"
    if net_score > -10:
        return "HOLD", "MEDIUM"
    if net_score > -30:
        return "AVOID", "LOW"
    return "STRONG_AVOID", "LOW"


class JudgeAgent(BaseAgent):
    """Synthesises bull and bear cases into a final, decisive verdict."""

    def __init__(self, name="JudgeAgent", qdrant_host="localhost", qdrant_port=6333):
        super().__init__(name, qdrant_host, qdrant_port)

    async def analyze(
        self,
        symbol: str,
        bull_case: dict,
        bear_case: dict,
        signal_recommendation: dict,
        kelly_sizing: dict = None,
    ) -> dict:
        bull_case = bull_case or {}
        bear_case = bear_case or {}
        signal_recommendation = signal_recommendation or {}
        kelly_sizing = kelly_sizing or {}

        bull_score = bull_case.get('score', 0)
        bear_score = bear_case.get('score', 0)
        net_score = bull_score - bear_score

        # VERDICT LOGIC:
        if net_score >= 35:
            verdict = 'STRONG_BUY'
            proceed = True
            confidence_score = min(95, 60 + net_score * 0.5)
            size_pct = 1.0
        elif net_score >= 15:
            verdict = 'PROCEED'
            proceed = True
            confidence_score = min(85, 55 + net_score * 0.5)
            size_pct = 0.8
        elif net_score >= 0:
            verdict = 'PROCEED_CAUTIOUSLY'
            proceed = True
            confidence_score = 50 + net_score
            size_pct = 0.5
        elif net_score >= -15:
            verdict = 'HOLD'
            proceed = False
            confidence_score = 50 - abs(net_score)
            size_pct = 0.0
        elif net_score >= -35:
            verdict = 'AVOID'
            proceed = False
            confidence_score = max(20, 45 - abs(net_score))
            size_pct = 0.0
        else:
            verdict = 'STRONG_AVOID'
            proceed = False
            confidence_score = max(10, 40 - abs(net_score))
            size_pct = 0.0

        from agents._llm import call_claude, llm_available
        reasoning = (f'Bull {bull_score:.0f} vs Bear {bear_score:.0f} = net {net_score:+.0f} → {verdict}')

        if llm_available():
            prompt = f'''
Symbol: {symbol}
Bull case ({bull_score:.0f}/100): {bull_case.get("reasoning", "")[:200]}
Bear case ({bear_score:.0f}/100): {bear_case.get("reasoning", "")[:200]}
Net score: {net_score:+.0f}
Preliminary verdict: {verdict}

In exactly 2 sentences, synthesize these
arguments into a final trading verdict.
Be decisive and specific.
'''
            llm_text = await call_claude(
                system='You are a trading judge. Synthesize bull and bear cases into a decisive verdict.',
                user=prompt,
                max_tokens=150
            )
            if llm_text:
                reasoning = llm_text

        position_value = 0.0
        if kelly_sizing and proceed:
            position_value = (kelly_sizing.get('position_value', 2500) * size_pct)

        return {
            'agent': 'judge',
            'symbol': symbol,
            'verdict': verdict,
            'net_score': round(net_score, 1),
            'bull_score': round(bull_score, 1),
            'bear_score': round(bear_score, 1),
            'confidence_score': round(confidence_score, 1),
            'reasoning': reasoning,
            'proceed': proceed,
            'recommended_size_pct': size_pct,
            'position_value': round(position_value, 2)
        }
