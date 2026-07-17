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
    """True only when a non-empty ANTHROPIC_API_KEY_AGENTS is configured."""
    return bool((os.getenv("ANTHROPIC_API_KEY_AGENTS") or "").strip())


async def call_claude(
    system: str,
    user: str,
    max_tokens: int = 320,
    temperature: float = 0.4,
) -> str | None:
    """Call Claude and return the concatenated text response, or None on failure.

    Includes error classification, bounded retry with exponential backoff for 
    transient errors, and a default timeout. Never raises — returns None on 
    failure so caller can fall back to rule-based logic.
    """
    if not llm_available():
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning("[LLM] anthropic package not found despite key present.")
        return None

    import asyncio

    api_key = os.getenv("ANTHROPIC_API_KEY_AGENTS")
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=15.0)

    max_attempts = 3
    initial_delay = 2.0
    backoff_factor = 2.0

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"[LLM] Calling Claude {CLAUDE_MODEL} (Attempt {attempt}/{max_attempts})...")
            resp = await client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=15.0,
            )
            text = "".join(
                block.text
                for block in resp.content
                if getattr(block, "type", None) == "text"
            ).strip()
            logger.info(f"[LLM] Response received: {text[:50]}...")
            return text or None

        except anthropic.AuthenticationError as exc:
            logger.critical(f"[LLM] CRITICAL: Authentication failed. Check your ANTHROPIC_API_KEY. Details: {exc}")
            break
        except anthropic.PermissionDeniedError as exc:
            logger.critical(f"[LLM] CRITICAL: Permission denied. Check billing/account status. Details: {exc}")
            break
        except anthropic.BadRequestError as exc:
            logger.critical(f"[LLM] CRITICAL: Bad Request (Invalid parameters/credits). Details: {exc}")
            break
        except anthropic.RateLimitError as exc:
            if attempt == max_attempts:
                logger.error(f"[LLM] Rate limit reached. All {max_attempts} attempts failed. Details: {exc}")
                break
            delay = initial_delay * (backoff_factor ** (attempt - 1))
            logger.warning(f"[LLM] Rate limit error (429) on attempt {attempt}. Retrying in {delay:.1f}s... Details: {exc}")
            await asyncio.sleep(delay)
        except anthropic.APIStatusError as exc:
            status_code = getattr(exc, "status_code", 500)
            if status_code >= 500:
                if attempt == max_attempts:
                    logger.error(f"[LLM] Server error ({status_code}). All {max_attempts} attempts failed. Details: {exc}")
                    break
                delay = initial_delay * (backoff_factor ** (attempt - 1))
                logger.warning(f"[LLM] Server error ({status_code}) on attempt {attempt}. Retrying in {delay:.1f}s... Details: {exc}")
                await asyncio.sleep(delay)
            else:
                logger.critical(f"[LLM] CRITICAL: Client-side API status error ({status_code}). Details: {exc}")
                break
        except anthropic.APIConnectionError as exc:
            if attempt == max_attempts:
                logger.error(f"[LLM] Connection failure. All {max_attempts} attempts failed. Details: {exc}")
                break
            delay = initial_delay * (backoff_factor ** (attempt - 1))
            logger.warning(f"[LLM] Connection/timeout error on attempt {attempt}. Retrying in {delay:.1f}s... Details: {exc}")
            await asyncio.sleep(delay)
        except Exception as exc:
            logger.error(f"[LLM] Unexpected exception on attempt {attempt}: {exc}", exc_info=True)
            if attempt == max_attempts:
                break
            delay = initial_delay * (backoff_factor ** (attempt - 1))
            await asyncio.sleep(delay)

    return None
