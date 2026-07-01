"""
Underlying bar data — load, resample, cache.

Precedence (highest fidelity first):
  1. Local parquet store (production ``/mnt/tick-storage/historical/equities``),
     the same store ``scripts/backtest_utbot.py`` reads.
  2. Alpaca ``StockHistoricalDataClient`` minute bars, cached to parquet.
  3. Deterministic SYNTHETIC bars — LAST RESORT so the harness is runnable and
     the tests are reproducible in a data-less / network-restricted sandbox.
     Loudly labeled ``SYNTHETIC`` in every run's Assumptions block.

Everything downstream consumes a tz-aware (America/New_York) OHLCV frame indexed
by timestamp, resampled to the requested timeframe and filtered to regular
trading hours (09:30-16:00 ET).
"""

from __future__ import annotations

import glob
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

ET = "America/New_York"

_TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15}


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize columns/index to OHLCV with a tz-aware DatetimeIndex (ET)."""
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if "timestamp" in df.columns:
        idx = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index(idx)
    elif "ts" in df.columns:
        idx = pd.to_datetime(df["ts"], utc=True)
        df = df.set_index(idx)
    elif isinstance(df.index, pd.DatetimeIndex):
        pass
    else:
        raise ValueError("No timestamp column or DatetimeIndex found")

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(ET)
    df.index.name = "timestamp"

    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].sort_index()
    return df


def _filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Keep regular trading hours 09:30-16:00 ET, weekdays only."""
    df = df[df.index.dayofweek < 5]
    t = df.index.time
    from datetime import time as _t

    mask = (t >= _t(9, 30)) & (t <= _t(16, 0))
    return df[mask]


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample 1m bars to the target timeframe, RTH aligned to :30 open."""
    minutes = _TF_MINUTES[timeframe]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "volume": "sum"}
    agg = {k: v for k, v in agg.items() if k in df.columns}
    # origin at 09:30 so bars align to the session open (15m -> 9:30,9:45,...)
    out = df.resample(f"{minutes}min", origin="start_day", offset="9h30min",
                      label="right", closed="right").agg(agg).dropna(subset=["close"])
    return _filter_rth(out)


# ─────────────────────────────────────────────────────────────────────────────
# Source 1: local parquet
# ─────────────────────────────────────────────────────────────────────────────
def _load_local(cfg) -> Optional[pd.DataFrame]:
    base = Path(cfg.data_store) / cfg.symbol
    if not base.exists():
        return None
    files = sorted(glob.glob(str(base / f"{cfg.symbol}_*.parquet")))
    if not files:
        return None
    frames = []
    for f in files:
        try:
            frames.append(pd.read_parquet(f))
        except Exception:
            continue
    if not frames:
        return None
    df = _standardize(pd.concat(frames))
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Source 2: Alpaca minute bars (cached)
# ─────────────────────────────────────────────────────────────────────────────
def _cache_path(cfg) -> Path:
    return Path(cfg.cache_dir) / f"{cfg.symbol}_1m_{cfg.start}_{cfg.end}.parquet"


def _load_alpaca(cfg, api_key: str, api_secret: str) -> Optional[pd.DataFrame]:  # pragma: no cover - network
    cache = _cache_path(cfg)
    if cache.exists():
        try:
            return _standardize(pd.read_parquet(cache))
        except Exception:
            pass
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(api_key, api_secret)
        req = StockBarsRequest(
            symbol_or_symbols=cfg.symbol,
            timeframe=TimeFrame.Minute,
            start=datetime(cfg.start.year, cfg.start.month, cfg.start.day),
            end=datetime(cfg.end.year, cfg.end.month, cfg.end.day),
        )
        bars = client.get_stock_bars(req).df
        if bars is None or len(bars) == 0:
            return None
        bars = bars.reset_index()
        df = _standardize(bars)
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache)
        return df
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Source 3: deterministic synthetic bars (last resort)
# ─────────────────────────────────────────────────────────────────────────────
def _synthetic(cfg) -> pd.DataFrame:
    """Reproducible GBM minute bars over RTH — SYNTHETIC, for demo/tests only.

    Seeded so every run/CI produces identical output. Parameters chosen to look
    like IWM (~$200, ~20% annualized vol) so the signal and cost model exercise
    realistic magnitudes.
    """
    rng = np.random.default_rng(42)
    sessions = pd.bdate_range(cfg.start, cfg.end, tz=ET)
    per_day = 390  # 1m RTH bars
    ann_vol = 0.20
    minute_vol = ann_vol / np.sqrt(252 * per_day)
    drift = 0.05 / (252 * per_day)  # mild upward drift

    price = 200.0
    rows = []
    for day in sessions:
        session_open = day.normalize() + pd.Timedelta(hours=9, minutes=30)
        # small overnight gap
        price *= float(np.exp(rng.normal(0, minute_vol * np.sqrt(per_day) * 0.3)))
        for m in range(per_day):
            ts = session_open + pd.Timedelta(minutes=m)
            ret = rng.normal(drift, minute_vol)
            new_price = price * float(np.exp(ret))
            o = price
            c = new_price
            hi = max(o, c) * (1 + abs(rng.normal(0, minute_vol)))
            lo = min(o, c) * (1 - abs(rng.normal(0, minute_vol)))
            vol = int(abs(rng.normal(50000, 15000)))
            rows.append((ts, o, hi, lo, c, vol))
            price = new_price

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.set_index("timestamp")
    df.index.name = "timestamp"
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Public loader
# ─────────────────────────────────────────────────────────────────────────────
def load_underlying(cfg, api_key: Optional[str] = None,
                    api_secret: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    """Return (resampled_ohlcv, source_label) for the configured window/timeframe."""
    source = None
    df = _load_local(cfg)
    if df is not None and len(df) > 0:
        source = f"local-parquet:{cfg.data_store}"
    elif api_key and api_secret:
        df = _load_alpaca(cfg, api_key, api_secret)
        if df is not None and len(df) > 0:
            source = "alpaca-minute-bars"

    if df is None or len(df) == 0:
        if not cfg.allow_synthetic:
            raise RuntimeError(
                "No underlying data available (no local store, no Alpaca) and "
                "synthetic data is disabled."
            )
        df = _synthetic(cfg)
        source = "SYNTHETIC (deterministic GBM — no real data available)"

    # window filter
    start_ts = pd.Timestamp(cfg.start, tz=ET)
    end_ts = pd.Timestamp(cfg.end, tz=ET) + pd.Timedelta(days=1)
    df = df[(df.index >= start_ts) & (df.index < end_ts)]

    resampled = resample(_filter_rth(df), cfg.timeframe)
    return resampled, source
