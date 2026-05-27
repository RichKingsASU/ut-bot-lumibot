"""
Shared LLM helper for the Bull/Bear/Judge debate agents.

Provides a thin async wrapper around the Anthropic SDK with a graceful
fallback: when ANTHROPIC_API_KEY is absent (or any error occurs), callers
get None back and fall through to rule-based logic. This lets the debate
layer run immediately and upgrade automatically once a key is added.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("DebateLLM")

# Model used for all debate reasoning. Override with ANTHROPIC_MODEL in .env.
CLAUDE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def llm_available() -> bool:
    """True only when a non-empty ANTHROPIC_API_KEY is configured."""
    return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())


async def call_claude(
    system: str,
    user: str,
    max_tokens: int = 320,
    temperature: float = 0.4,
) -> str | None:
    """Call Claude and return the concatenated text response, or None on failure.

    Never raises — any error (missing key, network, SDK) returns None so the
    caller can fall back to deterministic rule-based logic.
    """
    if not llm_available():
        return None

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        logger.info("[LLM] Calling Claude claude-sonnet-4-20250514...")
        resp = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text
            for block in resp.content
            if getattr(block, "type", None) == "text"
        ).strip()
        logger.info(f"[LLM] Response received: {text[:50]}...")
        return text or None
    except Exception as exc:  # noqa: BLE001 — fallback must never break the pipeline
        logger.error(f"[LLM] API call failed: {exc}")
        return None
