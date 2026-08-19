"""Validation boundaries for bars, quotes, sentiment, risk and agent decisions."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .data_validity import DataStatus, ValidatedValue, parse_timestamp

MAX_5M_DATA_AGE_SECONDS = 360
MAX_OPTION_QUOTE_AGE_SECONDS = 30
MAX_SENTIMENT_AGE_SECONDS = 3600


def validate_bars(rows: Sequence[Mapping[str, Any]] | None, *, source: str,
                  expected_symbol: str, expected_timeframe: str,
                  max_age_seconds: float, now: datetime | None = None) -> ValidatedValue[list[dict]]:
    now = now or datetime.now(timezone.utc)
    if not rows:
        return ValidatedValue(None, DataStatus.NO_DATA, None, source, "empty bars", now)
    required = {"open", "high", "low", "close", "timestamp"}
    normalized = []
    for row in rows:
        if not required.issubset(row):
            return ValidatedValue(None, DataStatus.MALFORMED, None, source, "required bar field missing", now)
        if row.get("symbol", expected_symbol) != expected_symbol or row.get("timeframe", expected_timeframe) != expected_timeframe:
            return ValidatedValue(None, DataStatus.MALFORMED, None, source, "bar identity mismatch", now)
        ts = parse_timestamp(row["timestamp"])
        try:
            o, h, low, close = (float(row[k]) for k in ("open", "high", "low", "close"))
        except (TypeError, ValueError):
            return ValidatedValue(None, DataStatus.MALFORMED, ts, source, "non-numeric price", now)
        if ts is None or not all(math.isfinite(x) and x > 0 for x in (o, h, low, close)) or h < low:
            return ValidatedValue(None, DataStatus.MALFORMED, ts, source, "invalid timestamp or OHLC", now)
        normalized.append({**row, "timestamp": ts, "open": o, "high": h, "low": low, "close": close})
    latest = max(r["timestamp"] for r in normalized)
    age = (now - latest.astimezone(timezone.utc)).total_seconds()
    if age < -60:
        return ValidatedValue(None, DataStatus.MALFORMED, latest, source, "future bar timestamp", now)
    if age > max_age_seconds:
        return ValidatedValue(None, DataStatus.STALE, latest, source, f"bar age {age:.0f}s exceeds {max_age_seconds:.0f}s", now)
    return ValidatedValue(normalized, DataStatus.VALID, latest, source, observed_at=now)


def validate_option_quote(quote: Mapping[str, Any] | None, *, contract: str,
                          max_age_seconds: float = MAX_OPTION_QUOTE_AGE_SECONDS,
                          max_spread_pct: float = .25,
                          now: datetime | None = None) -> ValidatedValue[dict]:
    now = now or datetime.now(timezone.utc)
    if not quote:
        return ValidatedValue(None, DataStatus.NO_QUOTE, None, "ALPACA_OPTION_QUOTE", "quote absent", now)
    ts = parse_timestamp(quote.get("timestamp") or quote.get("t"))
    if ts is None or quote.get("contract", contract) != contract:
        return ValidatedValue(None, DataStatus.MALFORMED, ts, "ALPACA_OPTION_QUOTE", "timestamp missing or contract mismatch", now)
    try:
        bid, ask = float(quote.get("bid", quote.get("bp"))), float(quote.get("ask", quote.get("ap")))
    except (TypeError, ValueError):
        return ValidatedValue(None, DataStatus.MALFORMED, ts, "ALPACA_OPTION_QUOTE", "non-numeric quote", now)
    if bid <= 0:
        return ValidatedValue(None, DataStatus.ZERO_BID, ts, "ALPACA_OPTION_QUOTE", "bid must be positive", now)
    if ask <= 0:
        return ValidatedValue(None, DataStatus.MALFORMED, ts, "ALPACA_OPTION_QUOTE", "ask must be positive", now)
    if ask < bid:
        return ValidatedValue(None, DataStatus.CROSSED_QUOTE, ts, "ALPACA_OPTION_QUOTE", "ask below bid", now)
    mid = (bid + ask) / 2
    if (ask - bid) / mid > max_spread_pct:
        return ValidatedValue(None, DataStatus.INVALID_SPREAD, ts, "ALPACA_OPTION_QUOTE", "spread exceeds entry limit", now)
    if (now - ts.astimezone(timezone.utc)).total_seconds() > max_age_seconds:
        return ValidatedValue(None, DataStatus.STALE_QUOTE, ts, "ALPACA_OPTION_QUOTE", "quote expired", now)
    return ValidatedValue({**quote, "bid": bid, "ask": ask, "mid": mid}, DataStatus.VALID, ts, "ALPACA_OPTION_QUOTE", observed_at=now)


def aggregate_sentiment(articles: Sequence[Mapping[str, Any]] | None, *, fetched_count: int,
                        source: str = "FINNHUB", error: str | None = None,
                        disabled: bool = False, max_age_seconds: float = MAX_SENTIMENT_AGE_SECONDS,
                        now: datetime | None = None) -> ValidatedValue[dict]:
    now = now or datetime.now(timezone.utc)
    if disabled:
        return ValidatedValue(None, DataStatus.DISABLED, None, source, "provider not configured", now)
    if error:
        return ValidatedValue(None, DataStatus.ERROR, None, source, error, now)
    scored = [a for a in (articles or []) if a.get("score") is not None and parse_timestamp(a.get("timestamp"))]
    if not scored:
        return ValidatedValue(None, DataStatus.NO_DATA, None, source, f"{fetched_count} fetched, 0 scored", now)
    newest = max(parse_timestamp(a["timestamp"]) for a in scored)
    payload = {"avg_sentiment": sum(float(a["score"]) for a in scored) / len(scored),
               "articles_fetched": fetched_count, "articles_scored": len(scored)}
    if (now - newest.astimezone(timezone.utc)).total_seconds() > max_age_seconds:
        return ValidatedValue(None, DataStatus.STALE, newest, source, "sentiment aggregation expired", now)
    return ValidatedValue(payload, DataStatus.VALID, newest, source, observed_at=now)


def validate_risk_value(value: Any, *, source: str, timestamp: Any,
                        positive: bool = False, error: str | None = None,
                        max_age_seconds: float = 30, now: datetime | None = None) -> ValidatedValue[float]:
    now = now or datetime.now(timezone.utc); ts = parse_timestamp(timestamp)
    if error:
        return ValidatedValue(None, DataStatus.ERROR, ts, source, error, now)
    try: number = float(value)
    except (TypeError, ValueError):
        return ValidatedValue(None, DataStatus.NO_DATA if value is None else DataStatus.MALFORMED, ts, source, "value unavailable", now)
    if not math.isfinite(number) or (positive and number <= 0) or ts is None:
        return ValidatedValue(None, DataStatus.MALFORMED, ts, source, "invalid risk value", now)
    if (now - ts.astimezone(timezone.utc)).total_seconds() > max_age_seconds:
        return ValidatedValue(None, DataStatus.STALE, ts, source, "risk value expired", now)
    return ValidatedValue(number, DataStatus.VALID, ts, source, observed_at=now)


def validate_agent_decision(value: str | None, *, required: bool, error: str | None = None) -> ValidatedValue[str]:
    now = datetime.now(timezone.utc)
    if error:
        return ValidatedValue(None, DataStatus.ERROR, now, "AGENT", error, now)
    if value not in {"BUY", "SELL", "HOLD", "PROCEED"}:
        return ValidatedValue(None, DataStatus.MALFORMED, now, "AGENT", "decision unavailable or malformed", now)
    return ValidatedValue(value, DataStatus.VALID, now, "AGENT", "required" if required else "optional", now)


def format_sentiment(value: ValidatedValue[dict]) -> str:
    if value.valid:
        p = value.value
        return f"Sentiment: {p['avg_sentiment']:.4f} ({p['articles_scored']} scored articles) [VALID]"
    scored = value.value.get("articles_scored", 0) if value.value else 0
    return f"Sentiment: {value.status.value} ({scored} scored articles)"
