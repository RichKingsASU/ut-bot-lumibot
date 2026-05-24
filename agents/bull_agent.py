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
        signal = signal_recommendation or {}
        greeks = greeks_context or {}
        regime_summary = regime_summary or {}

        # ── Extract inputs (resilient to missing fields) ──────────────────────
        sentiment = float(
            market_context.get("avg_sentiment", signal.get("sentiment_score", 0.0)) or 0.0
        )
        regime = str(
            regime_summary.get("overall_regime")
            or market_context.get("current_regime")
            or "QUIET"
        ).upper()
        action = str(signal.get("action", "HOLD")).upper()
        buy_sig = _truthy(signal.get("buy_sig", action == "BUY"))
        signal_type = str(signal.get("technical_signal", action))
        iv_rank = float(greeks.get("iv_rank", signal.get("iv_rank", 50.0)) or 50.0)
        rvol = float(greeks.get("rvol", 1.0) or 1.0)
        headlines = market_context.get("top_headlines", []) or []

        # ── Rule-based bull score ─────────────────────────────────────────────
        score = 0
        key_factors: list[str] = []

        if sentiment > 0.2:
            score += 25
            key_factors.append(f"Positive sentiment ({sentiment:.2f})")
        if regime in _BULLISH_REGIMES:
            score += 25
            key_factors.append(f"Bullish regime ({regime})")
        if buy_sig:
            score += 25
            key_factors.append("Active buy signal")
        if iv_rank < 30:
            score += 15
            key_factors.append(f"Cheap options — low IV rank ({iv_rank:.0f})")
        if rvol > 2.5:
            score += 10
            key_factors.append(f"High RVOL {rvol:.1f}x — institutional interest")

        if not key_factors:
            key_factors.append("No strong bullish factors present")

        reasoning = (
            f"Bull case: sentiment={sentiment:.2f}, regime={regime}, "
            f"signal={signal_type}, IV rank={iv_rank:.0f}, RVOL={rvol:.1f}x."
        )

        # ── LLM upgrade (optional) ────────────────────────────────────────────
        if llm_available():
            llm_text = await call_claude(
                system=_SYSTEM_PROMPT,
                user=self._format_context(
                    symbol, sentiment, regime, signal_type, buy_sig,
                    iv_rank, rvol, headlines,
                ),
            )
            if llm_text:
                reasoning = llm_text
                logger.info(f"[Bull] {symbol}: LLM reasoning generated.")

        result = {
            "agent": "bull",
            "symbol": symbol,
            "score": float(score),
            "reasoning": reasoning,
            "key_factors": key_factors,
            "confidence": _confidence_from_score(score),
        }
        logger.info(f"[Bull] {symbol}: score={score} confidence={result['confidence']}")
        return result

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
