"""Dependency-light, deterministic calculations shared by UT Bot runtimes."""

from __future__ import annotations

import pandas as pd


def daily_bar_is_stale(last_bar_time, now, max_age_days: int = 5):
    """Return whether a daily bar's session date is older than the limit."""
    age_days = (now.date() - last_bar_time.date()).days
    return age_days > max_age_days, age_days


# Backward-compatible private name used by existing callers.
_daily_bar_is_stale = daily_bar_is_stale


def calculate_ut_bot_signals(
    df: pd.DataFrame, atr_period: int = 10, sensitivity: float = 1.0
) -> pd.DataFrame:
    """Add the production UT Bot ATR, trailing-stop, and signal columns.

    The input is mutated and returned, matching the legacy strategy's behavior.
    """
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = abs(df["high"] - df["close"].shift())
    df["low_close"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)
    df["atr"] = df["tr"].rolling(window=atr_period).mean()

    df["loss"] = sensitivity * df["atr"]
    df["trail_stop"] = 0.0

    for i in range(1, len(df)):
        close = df.iloc[i]["close"]
        prev_close = df.iloc[i - 1]["close"]
        prev_trail_stop = df.iloc[i - 1]["trail_stop"]
        loss = df.iloc[i]["loss"]

        if close > prev_trail_stop and prev_close > prev_trail_stop:
            df.at[df.index[i], "trail_stop"] = max(prev_trail_stop, close - loss)
        elif close < prev_trail_stop and prev_close < prev_trail_stop:
            df.at[df.index[i], "trail_stop"] = min(prev_trail_stop, close + loss)
        elif close > prev_trail_stop:
            df.at[df.index[i], "trail_stop"] = close - loss
        else:
            df.at[df.index[i], "trail_stop"] = close + loss

    df["prev_trail_stop"] = df["trail_stop"].shift()
    df["signal"] = 0
    df.loc[
        (df["close"] > df["trail_stop"])
        & (df["close"].shift() <= df["prev_trail_stop"]),
        "signal",
    ] = 1
    df.loc[
        (df["close"] < df["trail_stop"])
        & (df["close"].shift() >= df["prev_trail_stop"]),
        "signal",
    ] = -1
    return df
