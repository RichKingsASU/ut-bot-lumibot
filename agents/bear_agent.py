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
        sell_sig = _truthy(signal.get("sell_sig", action == "SELL"))
        signal_type = str(signal.get("technical_signal", action))
        iv_rank = float(greeks.get("iv_rank", signal.get("iv_rank", 50.0)) or 50.0)
        rvol = float(greeks.get("rvol", 1.0) or 1.0)
        gamma = float(greeks.get("gamma", signal.get("gamma", 0.0)) or 0.0)
        delta = float(greeks.get("delta", 0.0) or 0.0)
        headlines = market_context.get("top_headlines", []) or []

        # ── Rule-based bear score ─────────────────────────────────────────────
        score = 0
        key_risks: list[str] = []

        if sentiment < -0.2:
            score += 25
            key_risks.append(f"Negative sentiment ({sentiment:.2f})")
        if regime in _BEARISH_REGIMES:
            score += 25
            key_risks.append(f"Adverse regime ({regime})")
        if sell_sig:
            score += 25
            key_risks.append("Active sell signal")
        if iv_rank > 70:
            score += 15
            key_risks.append(f"Expensive options — high IV rank ({iv_rank:.0f})")
        if gamma > 0.05:
            score += 10
            key_risks.append(f"High gamma risk ({gamma:.4f})")

        # ── Non-scoring red flags (context for the judge) ─────────────────────
        if buy_sig and sell_sig:
            key_risks.append("Conflicting buy/sell signals")
        if rvol < 1.0:
            key_risks.append(f"Low RVOL {rvol:.1f}x — no institutional interest")
        if abs(delta) >= 0.8:
            key_risks.append(f"Delta exposure near limit ({delta:.2f})")

        if not key_risks:
            key_risks.append("No strong bearish factors present")

        reasoning = (
            f"Bear case: sentiment={sentiment:.2f}, regime={regime}, "
            f"signal={signal_type}, IV rank={iv_rank:.0f}, gamma={gamma:.4f}, "
            f"RVOL={rvol:.1f}x."
        )

        # ── LLM upgrade (optional) ────────────────────────────────────────────
        if llm_available():
            llm_text = await call_claude(
                system=_SYSTEM_PROMPT,
                user=self._format_context(
                    symbol, sentiment, regime, signal_type, sell_sig,
                    iv_rank, rvol, gamma, delta, headlines,
                ),
            )
            if llm_text:
                reasoning = llm_text
                logger.info(f"[Bear] {symbol}: LLM reasoning generated.")

        result = {
            "agent": "bear",
            "symbol": symbol,
            "score": float(score),
            "reasoning": reasoning,
            "key_risks": key_risks,
            "confidence": _confidence_from_score(score),
        }
        logger.info(f"[Bear] {symbol}: score={score} confidence={result['confidence']}")
        return result

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
