"""Shared configuration and helpers for the Disrupting Alpha historical data system.

Used by:
  - seed_historical.py   (bulk backfill from Alpaca -> Parquet)
  - daily_updater.py     (incremental daily append, cron-driven)
  - data_inventory.py    (coverage report: local vs Alpaca)

Real-world Alpaca availability discovered during the data audit (2026-05-23):
  - Equities (SPY/IWM/QQQ) daily/minute bars start ~2016-01-04, NOT 2010.
  - Crypto (BTC/ETH/SOL) bars start ~2021-01-01, NOT 2020.
Requests for earlier dates simply return empty chunks, which are skipped.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests
from dotenv import load_dotenv

from alpaca.data.historical import (
    CryptoHistoricalDataClient,
    StockHistoricalDataClient,
)
from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# --------------------------------------------------------------------------- #
# Paths / env
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

STORAGE_ROOT = Path("/mnt/tick-storage")
HIST_ROOT = STORAGE_ROOT / "historical"
EQUITIES_ROOT = HIST_ROOT / "equities"
CRYPTO_ROOT = HIST_ROOT / "crypto"
DAILY_UPDATES_ROOT = STORAGE_ROOT / "daily_updates"
BACKTEST_RESULTS_ROOT = STORAGE_ROOT / "backtest_results"

# Total usable capacity of the 8TB drive, for inventory headroom reporting.
DRIVE_CAPACITY_TB = 7.2

# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #
# Chat ID fixed by the project spec (Richard's channel).
TELEGRAM_CHAT_ID = "8641189809"


def send_telegram(message: str) -> bool:
    """Blocking POST to Telegram. Returns True on success, never raises."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.warning("[telegram] TELEGRAM_BOT_TOKEN not set — skipping message")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=15,
        )
        if resp.status_code != 200:
            logging.warning("[telegram] failed (%s): %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - telemetry must never crash the job
        logging.warning("[telegram] error sending message: %s", exc)
        return False


# --------------------------------------------------------------------------- #
# Symbol universe & seed plan
# --------------------------------------------------------------------------- #
EQUITY_SYMBOLS = ["SPY", "IWM", "QQQ"]
CRYPTO_SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD"]

# Requested start dates per the project spec. Alpaca will return less if it
# has no data that far back; empty chunks are skipped gracefully.
EQUITY_DAILY_START = date(2010, 1, 1)
EQUITY_MINUTE_START = date(2020, 1, 1)
CRYPTO_DAILY_START = date(2020, 1, 1)
CRYPTO_MINUTE_START = date(2021, 1, 1)

# Timeframe labels used in filenames.
TF_DAILY_LABEL = "1D"
TF_MINUTE_LABEL = "1m"

# Optional stock data feed (sip requires entitlement; the project's ingester
# uses sip, so we try it and fall back to the Alpaca default on error).
STOCK_FEED = os.getenv("ALPACA_DATA_FEED", "sip").lower() or None


def fs_symbol(symbol: str) -> str:
    """Filesystem-safe symbol: 'BTC/USD' -> 'BTCUSD'."""
    return symbol.replace("/", "")


def symbol_dir(symbol: str, is_crypto: bool) -> Path:
    """Directory holding a symbol's Parquet files."""
    root = CRYPTO_ROOT if is_crypto else EQUITIES_ROOT
    return root / fs_symbol(symbol)


# --------------------------------------------------------------------------- #
# Alpaca clients
# --------------------------------------------------------------------------- #
def get_stock_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_API_SECRET")
    )


def get_crypto_client() -> CryptoHistoricalDataClient:
    return CryptoHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_API_SECRET")
    )


# --------------------------------------------------------------------------- #
# DataFrame normalisation
# --------------------------------------------------------------------------- #
COLUMNS = ["symbol", "ts", "open", "high", "low", "close", "volume", "trade_count", "vwap"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten Alpaca's (symbol, timestamp) MultiIndex df to a stable schema."""
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUMNS)
    out = df.reset_index().rename(columns={"timestamp": "ts"})
    for col in COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out = out[COLUMNS].sort_values("ts").reset_index(drop=True)
    return out


def fetch_stock_bars(
    client: StockHistoricalDataClient,
    symbol: str,
    timeframe: TimeFrame,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch stock bars, trying the configured feed then falling back."""
    kwargs = dict(symbol_or_symbols=[symbol], timeframe=timeframe, start=start, end=end)
    for feed in ([STOCK_FEED, None] if STOCK_FEED else [None]):
        try:
            req = StockBarsRequest(**kwargs, feed=feed) if feed else StockBarsRequest(**kwargs)
            return _normalize(client.get_stock_bars(req).df)
        except Exception as exc:  # noqa: BLE001
            if feed is not None:
                logging.warning(
                    "[alpaca] %s %s feed=%s failed (%s) — retrying default feed",
                    symbol, timeframe, feed, str(exc)[:120],
                )
                continue
            raise
    return pd.DataFrame(columns=COLUMNS)


def fetch_crypto_bars(
    client: CryptoHistoricalDataClient,
    symbol: str,
    timeframe: TimeFrame,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    req = CryptoBarsRequest(
        symbol_or_symbols=[symbol], timeframe=timeframe, start=start, end=end
    )
    return _normalize(client.get_crypto_bars(req).df)


# --------------------------------------------------------------------------- #
# Parquet I/O
# --------------------------------------------------------------------------- #
def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False, compression="snappy")


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path, engine="pyarrow")


def file_size_mb(path: Path) -> float:
    return path.stat().st_size / 1_000_000


def dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def modified_today(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime).date()
    return mtime == date.today()


# --------------------------------------------------------------------------- #
# Date chunking
# --------------------------------------------------------------------------- #
def _utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def year_chunks(start: date, end: date) -> Iterator[tuple[datetime, datetime]]:
    """Yield (start, end) UTC datetimes, one calendar year at a time."""
    cur = start
    while cur <= end:
        chunk_end = min(date(cur.year, 12, 31), end)
        yield _utc(cur), _utc(chunk_end) + timedelta(days=1) - timedelta(seconds=1)
        cur = date(cur.year + 1, 1, 1)


def month_chunks(start: date, end: date) -> Iterator[tuple[int, int, datetime, datetime]]:
    """Yield (year, month, start_dt, end_dt) UTC, one calendar month at a time."""
    cur = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    while cur <= last:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        yield cur.year, cur.month, _utc(cur), _utc(nxt) - timedelta(seconds=1)
        cur = nxt


def month_is_complete(year: int, month: int) -> bool:
    """True if the entire calendar month is in the past (immutable history)."""
    today = date.today()
    if month == 12:
        month_after = date(year + 1, 1, 1)
    else:
        month_after = date(year, month + 1, 1)
    return month_after <= today


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    return logging.getLogger(name)
