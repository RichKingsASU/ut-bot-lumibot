"""SPY gap lookup using the market-data API, never the broker endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import requests

from .data_validity import DataStatus, ValidatedValue, parse_timestamp


def check_gap(symbol: str, *, session_open: float | None = None) -> ValidatedValue[float]:
    source = "ALPACA_MARKET_DATA"
    url = f"{os.getenv('ALPACA_DATA_URL', 'https://data.alpaca.markets')}/v2/stocks/{symbol}/bars"
    headers = {"APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
               "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET", "")}
    try:
        response = requests.get(url, headers=headers, params={"timeframe": "1Day", "limit": 2}, timeout=10)
        response.raise_for_status()
        bars = response.json().get("bars")
    except Exception as exc:
        return ValidatedValue(None, DataStatus.ERROR, None, source, f"market-data request failed: {type(exc).__name__}")
    if not bars:
        return ValidatedValue(None, DataStatus.NO_DATA, None, source, "HTTP response contained no bars")
    try:
        previous_close = float(bars[-2]["c"] if len(bars) > 1 else bars[-1]["c"])
        opening = float(session_open if session_open is not None else bars[-1]["o"])
        ts = parse_timestamp(bars[-1]["t"])
        if previous_close <= 0 or opening <= 0 or ts is None:
            raise ValueError("invalid gap input")
        gap = (opening - previous_close) / previous_close
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return ValidatedValue(None, DataStatus.MALFORMED, None, source, str(exc))
    return ValidatedValue(gap, DataStatus.VALID, ts, source, observed_at=datetime.now(timezone.utc))
