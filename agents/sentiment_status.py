"""Sentiment data-status classification + enforcement policy.

Centralizes the four sentiment states so the collector-facing classifier
(``base_agent.get_recent_sentiment``) and the decision layer
(``signal_agent``) agree on semantics.

States
------
OK       real scored articles within the freshness window (avg_sentiment is a float)
NO_DATA  query succeeded but returned zero usable scored articles (system failure)
ERROR    the sentiment fetch/scoring itself failed (exception / API error)
STALE    data exists but the newest scored article is older than the staleness window

``avg_sentiment`` is only trustworthy when status == OK. For every other state it
is None, so a 0.0 can no longer masquerade as "missing".

Downstream policy
-----------------
NO_DATA / ERROR -> HOLD/BLOCK (do not trade on missing/failed sentiment)
STALE           -> DEGRADE (proceed on technicals at reduced conviction, flag it)
OK              -> normal behavior

Per-asset enforcement: crypto enforces the hard-block by default because its news
is reliably scored. Equities defaults to degrade-only (``enforces_block`` False)
because the live scorer does not yet score equities news; flip
``SENTIMENT_ENFORCE_EQUITIES=true`` once the scorer is fixed/verified.
"""
import os

# ── Status values ────────────────────────────────────────────────────────────
OK = "OK"
NO_DATA = "NO_DATA"
ERROR = "ERROR"
STALE = "STALE"

MISSING_STATES = (NO_DATA, ERROR)


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# Freshness window: how far back we look for ANY usable scored article.
FRESHNESS_HOURS = _get_int("SENTIMENT_FRESHNESS_HOURS", 24)

# Staleness window: the newest scored article must be at least this fresh to count
# as OK. Older-but-present scored data is STALE (degrade only — never a block).
STALENESS_MIN = _get_int("SENTIMENT_STALENESS_MIN", 15)

# Per-asset enforcement of the hard-block on NO_DATA / ERROR.
_ENFORCE = {
    "crypto": _get_bool("SENTIMENT_ENFORCE_CRYPTO", True),
    "equities": _get_bool("SENTIMENT_ENFORCE_EQUITIES", False),
}


def enforces_block(asset_class: str) -> bool:
    """Whether NO_DATA / ERROR should HARD-BLOCK (HOLD) for this asset class.

    When False, missing/failed sentiment DEGRADES instead of blocking. Defaults
    to True for unknown asset classes (fail safe toward not trading on phantom
    inputs).
    """
    return _ENFORCE.get((asset_class or "").lower(), True)


def is_missing(status: str) -> bool:
    """True for the states that represent genuinely missing/failed sentiment."""
    return status in MISSING_STATES
