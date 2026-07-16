import asyncio
import os
import json
import logging
import re
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
ALPACA_DATA_URL   = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")
NATS_URL          = os.getenv("NATS_URL", "nats://localhost:4222")

# ── Options chain feed config ─────────────────────────────────────────────────
# The reference endpoint (/v2/options/contracts) only returns contract
# DEFINITIONS — it never populates volume/bid/ask, so the worker dropped 100%
# of contracts. We pull live quotes/volume from the market-data snapshot feed.
# 'indicative' is included on the Basic data plan (OPRA is not required because
# Greeks are solved locally via mibian downstream).
OPTIONS_FEED        = os.getenv("ALPACA_OPTIONS_FEED", "indicative")
# Bound the strike ladder to ±band around the underlying so we don't enrich the
# entire chain (snapshot returns the full ladder, paginated 1000/page).
STRIKE_BAND_PCT     = float(os.getenv("OPTIONS_STRIKE_BAND_PCT", "0.10"))
# Liquidity gate on daily volume. NOTE (flagged for review): the old gate was
# volume > 100, which drops everything near the open before volume accumulates
# (the prime-morning window). Defaulted to 0 so the pipeline writes real
# snapshots at all; tighten once verified during regular trading hours.
MIN_CONTRACT_VOLUME = int(os.getenv("OPTIONS_MIN_VOLUME", "0"))
# Safety cap on snapshot pagination (each page is up to 1000 contracts).
MAX_SNAPSHOT_PAGES  = 4

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


_OCC_RE = re.compile(r"^(?P<root>[A-Z]+)(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})"
                     r"(?P<cp>[CP])(?P<strike>\d{8})$")


def _parse_occ_symbol(occ: str) -> Optional[dict]:
    """
    Decode an OCC option symbol into strike / expiry / type.
    e.g. 'SPY260604C00722000' → strike 722.0, expiry '2026-06-04', type 'call'.
    Returns None if the symbol does not match the OCC layout.
    """
    m = _OCC_RE.match(occ or "")
    if not m:
        return None
    return {
        "strike":      int(m.group("strike")) / 1000.0,
        "expiry":      f"20{m.group('yy')}-{m.group('mm')}-{m.group('dd')}",
        "option_type": "call" if m.group("cp") == "C" else "put",
    }


async def _fetch_options_chain(
    symbol: str,
    client: httpx.AsyncClient,
    underlying_price: Optional[float] = None,
) -> list[dict]:
    """
    Pull live option snapshots from the Alpaca market-data feed and return a
    list of normalised contract dicts.

    Quote/volume come from the snapshot feed (the reference endpoint
    /v2/options/contracts never populates them). strike/expiry/type are decoded
    from the OCC symbol key, so no separate reference call is needed. The strike
    ladder is bounded to ±STRIKE_BAND_PCT around the underlying when known.
    """
    today = datetime.now(timezone.utc).date()
    # Next Friday (or today if it is Friday)
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    next_friday = today + timedelta(days=days_until_friday)

    url = f"{ALPACA_DATA_URL}/v1beta1/options/snapshots/{symbol}"
    headers = {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }
    params: dict = {
        "feed":                OPTIONS_FEED,
        "expiration_date_gte": today.isoformat(),
        "expiration_date_lte": next_friday.isoformat(),
        "limit":               1000,
    }
    if underlying_price and underlying_price > 0:
        params["strike_price_gte"] = round(underlying_price * (1 - STRIKE_BAND_PCT), 2)
        params["strike_price_lte"] = round(underlying_price * (1 + STRIKE_BAND_PCT), 2)

    # ── Paginate the snapshot feed (best-effort, capped) ──────────────────────
    snapshots: dict = {}
    page_token: Optional[str] = None
    for _ in range(MAX_SNAPSHOT_PAGES):
        if page_token:
            params["page_token"] = page_token
        try:
            resp = await client.get(url, headers=headers, params=params, timeout=15.0)
            resp.raise_for_status()
            raw = resp.json()
        except Exception as exc:
            logger.error("Options snapshot fetch failed for %s: %s", symbol, exc)
            break
        snapshots.update(raw.get("snapshots", {}) or {})
        page_token = raw.get("next_page_token")
        if not page_token:
            break

    if not snapshots:
        return []

    # ── Normalise each snapshot into the contract shape the calculator wants ──
    contracts: list[dict] = []
    for occ, snap in snapshots.items():
        try:
            parsed = _parse_occ_symbol(occ)
            if parsed is None:
                continue

            daily = snap.get("dailyBar")    or {}
            quote = snap.get("latestQuote") or {}
            trade = snap.get("latestTrade") or {}

            volume = int(daily.get("v") or 0)
            if volume < MIN_CONTRACT_VOLUME:
                continue

            bid = quote.get("bp")
            ask = quote.get("ap")
            if bid is not None and ask is not None and (float(bid) > 0 or float(ask) > 0):
                price = (float(bid) + float(ask)) / 2.0
            else:
                # fall back to last trade / daily close
                price = float(daily.get("c") or trade.get("p") or 0.0)

            if price <= 0:
                # no usable quote → mibian can't solve; skip dead contract
                continue

            contracts.append({
                "symbol":        occ,
                "strike":        parsed["strike"],
                "expiry":        parsed["expiry"],
                "option_type":   parsed["option_type"],
                "price":         price,
                "volume":        volume,
                "open_interest": int(snap.get("openInterest") or 0),
                "iv":            None,   # solved locally by mibian downstream
            })
        except (TypeError, ValueError, KeyError) as exc:
            logger.debug("Skipping malformed snapshot: %s — %s", occ, exc)
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
        contracts        = await _fetch_options_chain(symbol, client, underlying_price)

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

    try:
        from agents.greeks_agent import GreeksAgent
        g_agent = GreeksAgent("options-greeks", "equities")
        asyncio.create_task(g_agent.analyze())
        logger.info("Triggered background GreeksAgent scan for %s", symbol)
    except Exception as e:
        logger.error("Failed to trigger GreeksAgent scan for %s: %s", symbol, e)


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
