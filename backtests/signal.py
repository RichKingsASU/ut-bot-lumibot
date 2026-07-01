"""
UT Bot ATR signal — faithful reimplementation of the *production* signal.

SOURCE OF TRUTH: ``strategies/ut_bot.py`` (OFF-LIMITS for edits). The trailing
stop, crossover and RSI math below are replicated **verbatim** from that file so
the backtest fires the exact same signals the live bot would. Do NOT change the
math here; change it in production first (which the task forbids).

Two signal variants live in the repo:

  * ``strategies/ut_bot.py``            → SMA ATR + 4-branch trailing stop.
    This is what the live bot trades, so it is the canonical function used by
    the backtest engine: :func:`compute_ut_signal`.
  * ``scripts/backtest_utbot.py``       → EWM ATR + 2-branch trailing stop.
    Reproduced as :func:`calculate_ut_signals` purely so the unit tests can
    assert byte-for-byte parity against the reference implementation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Canonical production signal — verbatim from strategies/ut_bot.py
# ─────────────────────────────────────────────────────────────────────────────
def compute_ut_signal(
    df: pd.DataFrame,
    atr_period: int = 10,
    sensitivity: float = 1.0,
) -> pd.DataFrame:
    """Replicate the UT Bot signal from ``strategies/ut_bot.py`` verbatim.

    Returns a copy of ``df`` with ``atr``, ``trail_stop`` and ``signal``
    (+1 buy / -1 sell / 0) columns. Column math mirrors
    ``UTBotStrategy.on_trading_iteration`` lines 116-154.
    """
    df = df.copy()

    # ── ATR (SMA of true range) — ut_bot.py:117-121 ────────────────────
    df["high_low"] = df["high"] - df["low"]
    df["high_close"] = abs(df["high"] - df["close"].shift())
    df["low_close"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)
    df["atr"] = df["tr"].rolling(window=atr_period).mean()

    # ── Trailing stop (4-branch recursion) — ut_bot.py:123-140 ─────────
    df["loss"] = sensitivity * df["atr"]
    df["trail_stop"] = 0.0

    trail = np.zeros(len(df), dtype=float)
    close_arr = np.asarray(df["close"], dtype=float)
    loss_arr = np.asarray(df["loss"], dtype=float)
    for i in range(1, len(df)):
        close = close_arr[i]
        prev_close = close_arr[i - 1]
        prev_trail_stop = trail[i - 1]
        loss = loss_arr[i]

        if close > prev_trail_stop and prev_close > prev_trail_stop:
            trail[i] = max(prev_trail_stop, close - loss)
        elif close < prev_trail_stop and prev_close < prev_trail_stop:
            trail[i] = min(prev_trail_stop, close + loss)
        elif close > prev_trail_stop:
            trail[i] = close - loss
        else:
            trail[i] = close + loss
    df["trail_stop"] = trail

    # ── Crossover signal — ut_bot.py:142-154 ───────────────────────────
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


def compute_rsi_series(series: pd.Series, period: int = 14) -> pd.Series:
    """Rolling RSI matching ``UTBotStrategy._compute_rsi`` (ut_bot.py:288-299).

    The production method returns only the latest scalar; the backtest needs
    the RSI at every bar, so we vectorize the identical formula and evaluate it
    across the whole series. The last element equals the production scalar.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)  # ut_bot.py returns 50.0 when RSI is NaN


# ─────────────────────────────────────────────────────────────────────────────
# Reference vectorbt signal — verbatim from scripts/backtest_utbot.py
# (used ONLY for the signal-parity unit test)
# ─────────────────────────────────────────────────────────────────────────────
def calculate_ut_signals(df: pd.DataFrame, atr_period: int = 14, sensitivity: float = 1.0):
    """Verbatim copy of ``scripts/backtest_utbot.py::calculate_ut_signals``.

    Kept here so the test-suite can assert parity without importing vectorbt
    (which the reference script pulls in at module import time).
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(span=atr_period, adjust=False).mean()

    trail_stop = pd.Series(index=df.index, dtype=float)
    trail_stop.iloc[0] = close.iloc[0]

    for i in range(1, len(close)):
        prev_stop = trail_stop.iloc[i - 1]
        curr_close = close.iloc[i]
        curr_atr = atr.iloc[i] * sensitivity

        if curr_close > prev_stop:
            trail_stop.iloc[i] = max(prev_stop, curr_close - curr_atr)
        else:
            trail_stop.iloc[i] = min(prev_stop, curr_close + curr_atr)

    buy_sig = (close > trail_stop) & (close.shift() <= trail_stop.shift())
    sell_sig = (close < trail_stop) & (close.shift() >= trail_stop.shift())

    return buy_sig, sell_sig, trail_stop
