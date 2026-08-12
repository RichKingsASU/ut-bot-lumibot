import os
import requests
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import pytz
from dataclasses import dataclass
from typing import Optional, Dict

logger = logging.getLogger("signal_engine")
ET = pytz.timezone("America/New_York")

MAX_5M_BAR_AGE_SECONDS = 300  # Configurable 5m bar freshness limit
MAX_DAILY_BAR_AGE_HOURS = 24  # Max age for daily bars

@dataclass
class SignalSnapshot:
    valid: bool
    signal: int
    underlying_price: float
    rsi_5m: float
    trail_stop: float
    daily_bar_timestamp: Optional[datetime]
    intraday_bar_timestamp: Optional[datetime]
    reason: str

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "signal": self.signal,
            "underlying_price": self.underlying_price,
            "rsi_5m": self.rsi_5m,
            "trail_stop": self.trail_stop,
            "daily_bar_timestamp": self.daily_bar_timestamp.isoformat() if self.daily_bar_timestamp else None,
            "intraday_bar_timestamp": self.intraday_bar_timestamp.isoformat() if self.intraday_bar_timestamp else None,
            "reason": self.reason
        }

def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET", ""),
        "Content-Type": "application/json",
    }

def _data_url() -> str:
    return os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

def get_bars(symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    """Fetch bars using Alpaca v2 Data API."""
    url = f"{_data_url()}/v2/stocks/{symbol}/bars"
    # End is now, start is 20 days ago for daily, 2 days ago for 5Min
    now = datetime.now(ET)
    start = now - timedelta(days=20 if "Day" in timeframe else 2)
    params = {
        "timeframe": timeframe,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": limit
    }
    
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        bars = resp.json().get("bars", [])
        if not bars:
            return pd.DataFrame()
        
        df = pd.DataFrame(bars)
        df.rename(columns={"t": "time", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}, inplace=True)
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        return df
    except Exception as e:
        logger.error(f"Failed to fetch bars: {e}")
        return pd.DataFrame()

def compute_ut_bot(df: pd.DataFrame, atr_period: int = 10, sensitivity: float = 1.0) -> pd.DataFrame:
    if df.empty or len(df) < atr_period + 1:
        return df
        
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift())
    df['low_close'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=atr_period).mean()

    df['loss'] = sensitivity * df['atr']
    df['trail_stop'] = 0.0

    for i in range(1, len(df)):
        close = df.iloc[i]['close']
        prev_close = df.iloc[i-1]['close']
        prev_trail_stop = df.iloc[i-1]['trail_stop']
        loss = df.iloc[i]['loss']

        if close > prev_trail_stop and prev_close > prev_trail_stop:
            df.at[df.index[i], 'trail_stop'] = max(prev_trail_stop, close - loss)
        elif close < prev_trail_stop and prev_close < prev_trail_stop:
            df.at[df.index[i], 'trail_stop'] = min(prev_trail_stop, close + loss)
        elif close > prev_trail_stop:
            df.at[df.index[i], 'trail_stop'] = close - loss
        else:
            df.at[df.index[i], 'trail_stop'] = close + loss

    df['prev_trail_stop'] = df['trail_stop'].shift()
    df['signal'] = 0
    df.loc[
        (df['close'] > df['trail_stop']) &
        (df['close'].shift() <= df['prev_trail_stop']),
        'signal'
    ] = 1
    df.loc[
        (df['close'] < df['trail_stop']) &
        (df['close'].shift() >= df['prev_trail_stop']),
        'signal'
    ] = -1

    return df

def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    latest = rsi.iloc[-1]
    return float(latest) if not pd.isna(latest) else np.nan

def evaluate_signal(symbol: str) -> SignalSnapshot:
    """Evaluates the daily UT Bot signal and the 5-min RSI."""
    now = datetime.now(ET)
    
    # 1. Fetch Daily Bars
    df_daily = get_bars(symbol, "1Day", limit=100)
    if df_daily.empty:
        return SignalSnapshot(False, 0, 0.0, 0.0, 0.0, None, None, "DAILY_DATA_UNAVAILABLE")
        
    daily_ts = df_daily.index[-1]
    # In live execution (e.g. 15:45 ET), we might be fetching today's incomplete daily bar.
    if (now - daily_ts).total_seconds() > MAX_DAILY_BAR_AGE_HOURS * 3600:
        return SignalSnapshot(False, 0, 0.0, 0.0, 0.0, daily_ts, None, "STALE_DAILY_DATA")
    
    # 2. Fetch 5-Min Bars for RSI
    df_5m = get_bars(symbol, "5Min", limit=100)
    if df_5m.empty:
        return SignalSnapshot(False, 0, 0.0, 0.0, 0.0, daily_ts, None, "INTRADAY_DATA_UNAVAILABLE")
        
    intraday_ts = df_5m.index[-1]
    
    age_seconds = (now - intraday_ts).total_seconds()
    if age_seconds > MAX_5M_BAR_AGE_SECONDS:
        # Check if we are outside market hours (approx)
        if now.hour >= 16 or now.hour < 9 or (now.hour == 9 and now.minute < 30) or now.weekday() >= 5:
            pass # Accept stale data outside market hours for position management
        else:
            return SignalSnapshot(False, 0, 0.0, 0.0, 0.0, daily_ts, intraday_ts, f"STALE_5M_DATA")

    current_rsi = compute_rsi(df_5m['close'], 14)
    if np.isnan(current_rsi):
        return SignalSnapshot(False, 0, 0.0, 0.0, 0.0, daily_ts, intraday_ts, "MALFORMED_DATA_RSI")
    
    df_daily = compute_ut_bot(df_daily, 10, 1.0)
    
    latest = df_daily.iloc[-1]
    current_price = latest['close']
    current_signal = latest['signal']
    trail_stop = latest['trail_stop']
    
    if current_price <= 0 or np.isnan(current_price):
        return SignalSnapshot(False, 0, 0.0, 0.0, 0.0, daily_ts, intraday_ts, "INVALID_PRICE")
        
    return SignalSnapshot(
        valid=True,
        signal=int(current_signal),
        underlying_price=float(current_price),
        rsi_5m=float(current_rsi),
        trail_stop=float(trail_stop),
        daily_bar_timestamp=daily_ts,
        intraday_bar_timestamp=intraday_ts,
        reason="VALID_SIGNAL"
    )
