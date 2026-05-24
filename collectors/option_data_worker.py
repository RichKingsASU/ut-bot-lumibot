import asyncio
import os
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import pytz
from dotenv import load_dotenv
import nats
import httpx

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("OptionDataWorker")

# ── Environment ───────────────────────────────────────────────────────────────
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")
ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
NATS_URL          = os.getenv("NATS_URL", "nats://localhost:4222")

# ── Scan Tiers ────────────────────────────────────────────────────────────────
PRIORITY_1 = {"SPY": 60,  "QQQ": 60,  "IWM": 60}
PRIORITY_2 = {"NVDA": 300, "TSLA": 300, "AAPL": 300}
PRIORITY_3 = {"MSFT": 900, "META": 900, "GOOGL": 900}

ALL_SYMBOLS: dict[str, int] = {**PRIORITY_1, **PRIORITY_2, **PRIORITY_3}

# ── In-memory cache ───────────────────────────────────────────────────────────
_cache: dict[str, dict] = {}

# ── NATS connection (shared) ──────────────────────────────────────────────────
_nc = None


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_market_hours() -> bool:
    """Return True if the current Eastern time is a weekday between 09:30 and 16:00."""
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    if now.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now < market_close


def get_cached_greeks(symbol: str) -> Optional[dict]:
    """Return the cache entry for *symbol* if present and not stale, else None."""
    entry = _cache.get(symbol)
    if entry is None:
        return None

    ttl = ALL_SYMBOLS.get(symbol, 60)
    age = time.time() - entry.get("timestamp", 0)
    if age > ttl:
        logger.debug("Cache stale for %s (age=%.1fs, ttl=%ds)", symbol, age, ttl)
        return None

    return entry


# ─────────────────────────────────────────────────────────────────────────────
# NATS helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_nats() -> Optional[object]:
    """Return (and lazily create) a shared NATS connection."""
    global _nc
    if _nc is not None and not _nc.is_closed:
        return _nc
    try:
        _nc = await nats.connect(
            NATS_URL,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        logger.info("Connected to NATS at %s", NATS_URL)
    except Exception as exc:
        logger.error("NATS connect failed: %s", exc)
        _nc = None
    return _nc


async def _publish(subject: str, data: dict) -> None:
    """Publish *data* as JSON to *subject* via NATS (best-effort)."""
    nc = await _get_nats()
    if nc is None:
        return
    try:
        payload = json.dumps(data).encode("utf-8")
        await nc.publish(subject, payload)
    except Exception as exc:
        logger.error("Publish to %s failed: %s", subject, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Alpaca options chain fetch
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_underlying_price(symbol: str, client: httpx.AsyncClient) -> Optional[float]:
    """Fetch latest trade price for *symbol* from Alpaca data API."""
    data_url = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")
    url = f"{data_url}/v2/stocks/{symbol}/trades/latest"
    headers = {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }
    try:
        resp = await client.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("trade", {}).get("p", 0)) or None
    except Exception as exc:
        logger.warning("Could not fetch underlying price for %s: %s", symbol, exc)
        return None


async def _fetch_options_chain(symbol: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Pull options contracts from Alpaca REST API.
    Returns a list of normalised contract dicts filtered to volume > 100.
    """
    today = datetime.now(timezone.utc).date()
    # Next Friday (or today if it is Friday)
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    next_friday = today + timedelta(days=days_until_friday)

    url = f"{ALPACA_BASE_URL}/v2/options/contracts"
    headers = {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }
    params = {
        "underlying_symbols":    symbol,
        "expiration_date_gte":   today.isoformat(),
        "expiration_date_lte":   next_friday.isoformat(),
        "limit":                 100,
    }

    try:
        resp = await client.get(url, headers=headers, params=params, timeout=15.0)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        logger.error("Options chain fetch failed for %s: %s", symbol, exc)
        return []

    contracts_raw = raw.get("option_contracts", raw) if isinstance(raw, dict) else raw
    if not isinstance(contracts_raw, list):
        logger.warning("Unexpected response shape for %s: %s", symbol, type(raw))
        return []

    contracts: list[dict] = []
    for c in contracts_raw:
        try:
            volume = int(c.get("volume") or 0)
            if volume <= 100:
                continue

            bid = c.get("bid_price")
            ask = c.get("ask_price")
            close_price = float(c.get("close_price") or 0)

            if bid is not None and ask is not None:
                price = (float(bid) + float(ask)) / 2.0
            elif close_price:
                price = close_price
            else:
                price = 0.0

            contracts.append({
                "symbol":       c.get("symbol"),
                "strike":       float(c.get("strike_price") or 0),
                "expiry":       str(c.get("expiration_date", "")),
                "option_type":  str(c.get("type", c.get("option_type", ""))).lower(),
                "price":        price,
                "volume":       volume,
                "open_interest": int(c.get("open_interest") or 0),
                "iv":           float(c["implied_volatility"]) if c.get("implied_volatility") is not None else None,
            })
        except (TypeError, ValueError, KeyError) as exc:
            logger.debug("Skipping malformed contract: %s — %s", c.get("symbol"), exc)
            continue

    return contracts


# ─────────────────────────────────────────────────────────────────────────────
# Core scan
# ─────────────────────────────────────────────────────────────────────────────

async def scan_symbol(symbol: str, ttl: int) -> None:
    """
    Pull the options chain for *symbol*, update _cache, and publish to NATS.
    Does nothing when the market is closed.
    """
    if not is_market_hours():
        logger.info("Market closed — skipping scan for %s", symbol)
        return

    logger.info("Scanning %s (ttl=%ds)…", symbol, ttl)

    async with httpx.AsyncClient() as client:
        underlying_price = await _fetch_underlying_price(symbol, client)
        contracts        = await _fetch_options_chain(symbol, client)

    entry: dict = {
        "timestamp":        time.time(),
        "underlying_price": underlying_price or 0.0,
        "contracts":        contracts,
    }
    _cache[symbol] = entry

    subject = f"options.chain.{symbol}"
    await _publish(subject, {
        "symbol":           symbol,
        "timestamp":        entry["timestamp"],
        "underlying_price": entry["underlying_price"],
        "contracts":        contracts,
    })
    logger.info(
        "Cached %d contracts for %s (underlying=%.2f), published to %s",
        len(contracts), symbol, entry["underlying_price"], subject
    )


# ─────────────────────────────────────────────────────────────────────────────
# Priority loops
# ─────────────────────────────────────────────────────────────────────────────

async def _priority_loop(symbols: dict[str, int]) -> None:
    """
    Continuously scan a group of symbols at their specified TTL intervals.
    When the market is closed, logs and sleeps 60 s before rechecking.
    """
    while True:
        if not is_market_hours():
            logger.info("Market closed — sleeping 60s before next check")
            await asyncio.sleep(60)
            continue

        tasks = [scan_symbol(sym, ttl) for sym, ttl in symbols.items()]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Sleep for the shortest TTL in this group
        sleep_for = min(symbols.values())
        logger.debug("Priority loop sleeping %ds", sleep_for)
        await asyncio.sleep(sleep_for)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    """Run all three priority loops concurrently."""
    logger.info("OptionDataWorker starting — NATS=%s", NATS_URL)
    await asyncio.gather(
        _priority_loop(PRIORITY_1),
        _priority_loop(PRIORITY_2),
        _priority_loop(PRIORITY_3),
    )


if __name__ == "__main__":
    asyncio.run(main())
