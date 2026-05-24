"""
JudgeAgent — Disrupting Alpha v2 debate layer.

Weighs the bull and bear cases and renders a final verdict. The net score
(bull - bear) deterministically sets the baseline verdict; when an
ANTHROPIC_API_KEY is configured, Claude synthesises the reasoning and may
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
        signal = signal_recommendation or {}
        kelly_sizing = kelly_sizing or {}

        bull_score = float(bull_case.get("score", 0.0) or 0.0)
        bear_score = float(bear_case.get("score", 0.0) or 0.0)
        net_score = bull_score - bear_score

        verdict, confidence_modifier = _verdict_from_net(net_score)

        # Confidence scales with conviction (net score magnitude), centred at 50.
        confidence_score = max(0.0, min(100.0, 50.0 + net_score * 0.5))

        # Recommended size as a percentage of normal sizing for this verdict.
        recommended_size_pct = _SIZE_FRACTION.get(verdict, 0.0) * 100.0

        reasoning = (
            f"Bull {bull_score:.0f} vs Bear {bear_score:.0f} → net {net_score:+.0f}. "
            f"Verdict {verdict} ({confidence_modifier} conviction). "
            f"Bull: {str(bull_case.get('reasoning', '')).strip()[:120]} "
            f"Bear: {str(bear_case.get('reasoning', '')).strip()[:120]}"
        ).strip()
        key_insight = (
            f"{symbol}: bull-bear net {net_score:+.0f} favours "
            f"{'the long case' if net_score > 0 else 'caution'}."
        )

        # ── LLM synthesis (optional) ──────────────────────────────────────────
        if llm_available():
            llm_result = await self._llm_synthesis(symbol, bull_case, bear_case, net_score)
            if llm_result:
                # Trust the LLM for narrative; keep proceed grounded in net score
                # unless the LLM returns a recognised verdict.
                llm_verdict = str(llm_result.get("verdict", "")).upper().replace(" ", "_")
                if llm_verdict in _SIZE_FRACTION:
                    verdict = llm_verdict
                    recommended_size_pct = _SIZE_FRACTION[verdict] * 100.0
                if llm_result.get("reasoning"):
                    reasoning = str(llm_result["reasoning"]).strip()
                if llm_result.get("key_insight"):
                    key_insight = str(llm_result["key_insight"]).strip()
                try:
                    confidence_score = max(0.0, min(100.0, float(llm_result["confidence"])))
                except (KeyError, TypeError, ValueError):
                    pass
                logger.info(f"[Judge] {symbol}: LLM synthesis applied.")

        proceed = verdict in _PROCEED_VERDICTS

        result = {
            "agent": "judge",
            "symbol": symbol,
            "verdict": verdict,
            "net_score": float(net_score),
            "confidence_score": float(confidence_score),
            "reasoning": reasoning,
            "key_insight": key_insight,
            "bull_score": bull_score,
            "bear_score": bear_score,
            "recommended_size_pct": float(recommended_size_pct),
            "proceed": bool(proceed),
        }
        logger.info(
            f"[Judge] {symbol}: verdict={verdict} net={net_score:+.0f} "
            f"confidence={confidence_score:.0f}% proceed={proceed}"
        )
        return result

    async def _llm_synthesis(
        self, symbol: str, bull_case: dict, bear_case: dict, net_score: float,
    ) -> dict | None:
        """Ask Claude to synthesise a verdict; returns parsed JSON dict or None."""
        user = (
            f"Symbol: {symbol}\n"
            f"Net score (bull - bear): {net_score:+.0f}\n\n"
            f"BULL CASE (score {bull_case.get('score', 0)}):\n"
            f"{bull_case.get('reasoning', '')}\n"
            f"Key factors: {', '.join(bull_case.get('key_factors', [])) or 'none'}\n\n"
            f"BEAR CASE (score {bear_case.get('score', 0)}):\n"
            f"{bear_case.get('reasoning', '')}\n"
            f"Key risks: {', '.join(bear_case.get('key_risks', [])) or 'none'}\n\n"
            "Synthesize the final verdict. Valid verdict values: PROCEED, "
            "PROCEED_CAUTIOUSLY, HOLD, AVOID, STRONG_AVOID. "
            "Respond with ONLY a JSON object: "
            '{"verdict": "...", "reasoning": "...", "confidence": 0-100, '
            '"key_insight": "..."}'
        )
        raw = await call_claude(system=_SYSTEM_PROMPT, user=user, max_tokens=400)
        if not raw:
            return None
        try:
            # Tolerate fenced code blocks or surrounding prose by isolating the JSON.
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end < start:
                return None
            return json.loads(raw[start : end + 1])
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error(f"[Judge] {symbol}: failed to parse LLM JSON: {exc}")
            return None
