"""
UT Bot ATR Options Strategy — Lumibot Implementation.

Signal logic:
  - UT Bot ATR trailing stop generates LONG / SHORT direction
  - Entry: buy CALL (LONG) or PUT (SHORT) via Alpaca options API
  - Exit: RSI step-back, trailing stop on underlying, or EOD flatten

CONSTRAINTS:
  - Signal computation (trailing stop + crossover) is OFF-LIMITS for edits
  - ATR_PERIOD=10, ATR_MULT=1.0
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
import pytz
from lumibot.strategies.strategy import Strategy

from strategies.options_executor import (
    buy_to_open,
    sell_to_close,
    has_open_position,
    get_open_position,
    get_underlying_price,
)
from strategies.heartbeat import set_last_signal

logger = logging.getLogger("ut_bot_strategy")
ET = pytz.timezone("America/New_York")


class UTBotStrategy(Strategy):
    parameters = {
        "symbol": "SPY",
        "atr_period": 10,         # ATR_PERIOD=10 per spec
        "sensitivity": 1.0,       # ATR_MULT=1.0 per spec
        "timeframe": "1D",
        # ── Exit parameters ──
        "rsi_period": 14,
        "rsi_step_thresh": 5.0,   # RSI drop from entry to trigger exit
        "stop_pct": 0.005,        # 0.5% adverse move on underlying
        "eod_flatten_time": "15:55",  # ET time to flatten all positions
        # ── Position sizing ──
        "max_contracts": 1,
    }

    def initialize(self):
        self.sleeptime = "1M"  # 1-minute bars for intraday options
        self.last_signal = None
        self.last_direction = None

    def on_trading_iteration(self):
        symbol = self.parameters["symbol"]
        atr_period = self.parameters["atr_period"]
        sensitivity = self.parameters["sensitivity"]

        # ── Check EOD flatten FIRST (highest priority) ───────────────────
        if has_open_position():
            now_et = datetime.now(ET)
            flatten_h, flatten_m = map(int,
                self.parameters["eod_flatten_time"].split(":"))
            if now_et.hour > flatten_h or (
                now_et.hour == flatten_h and now_et.minute >= flatten_m
            ):
                logger.info("EOD flatten triggered at %s ET", now_et.strftime("%H:%M"))
                sell_to_close(exit_reason="eod_flatten")
                return

        # ── Fetch historical prices ──────────────────────────────────────
        bars = self.get_historical_prices(symbol, 100, "day")
        df = bars.df

        # ══════════════════════════════════════════════════════════════════
        # SIGNAL LOGIC — DO NOT MODIFY (off-limits per constraints)
        # ══════════════════════════════════════════════════════════════════

        # Calculate ATR manually
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift())
        df['low_close'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=atr_period).mean()

        # Calculate UT Bot Trailing Stop
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

        # Signal logic
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

        # ══════════════════════════════════════════════════════════════════
        # END SIGNAL LOGIC
        # ══════════════════════════════════════════════════════════════════

        current_price = df.iloc[-1]['close']
        current_signal = df.iloc[-1]['signal']

        # ── Compute 5-minute RSI for exit logic ──────────────────────────
        current_rsi = self._compute_rsi(df['close'], self.parameters["rsi_period"])

        # ── Determine direction ──────────────────────────────────────────
        if current_signal == 1:
            self.last_direction = "LONG"
        elif current_signal == -1:
            self.last_direction = "SHORT"

        self.log_message(
            f"Price: {current_price:.2f} | Signal: {current_signal} | "
            f"Dir: {self.last_direction} | RSI: {current_rsi:.1f} | "
            f"Position: {has_open_position()}"
        )

        # ── EXIT LOGIC (if we have an open position) ────────────────────
        if has_open_position():
            pos = get_open_position()
            exit_reason = self._check_exit_triggers(
                current_price, current_rsi, pos
            )
            if exit_reason:
                logger.info("Exit triggered: %s", exit_reason)
                sell_to_close(exit_reason=exit_reason)
                return

        # ── ENTRY LOGIC (if no open position) ───────────────────────────
        if not has_open_position() and current_signal != 0:
            direction = "LONG" if current_signal == 1 else "SHORT"
            signal_label = "CALL" if direction == "LONG" else "PUT"
            logger.info("Entry signal: %s at underlying=%.2f RSI=%.1f",
                        direction, current_price, current_rsi)
            buy_to_open(
                underlying=symbol,
                direction=direction,
                qty=self.parameters["max_contracts"],
                underlying_price=current_price,
                current_rsi=current_rsi,
            )
            set_last_signal(signal_label)

    # ── Exit trigger evaluation ──────────────────────────────────────────

    def _check_exit_triggers(self, current_price: float,
                              current_rsi: float, pos: dict) -> str | None:
        """
        Check all three exit conditions. Returns the reason string or None.
        Priority: EOD flatten is checked earlier (top of on_trading_iteration).
        """
        # 1. RSI step-back
        entry_rsi = pos.get("entry_rsi")
        if entry_rsi is not None:
            rsi_drop = entry_rsi - current_rsi
            if rsi_drop >= self.parameters["rsi_step_thresh"]:
                return f"rsi_stepback (entry={entry_rsi:.1f} now={current_rsi:.1f})"

        # 2. Trailing stop on underlying price
        entry_price = pos.get("entry_underlying_price", current_price)
        stop_pct = self.parameters["stop_pct"]
        if pos.get("direction") == "LONG":
            if current_price <= entry_price * (1 - stop_pct):
                return f"trailing_stop_long (entry={entry_price:.2f} now={current_price:.2f})"
        elif pos.get("direction") == "SHORT":
            if current_price >= entry_price * (1 + stop_pct):
                return f"trailing_stop_short (entry={entry_price:.2f} now={current_price:.2f})"

        return None

    # ── RSI calculation ──────────────────────────────────────────────────

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int = 14) -> float:
        """Compute RSI from a price series. Returns the latest RSI value."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        latest = rsi.iloc[-1]
        return float(latest) if not np.isnan(latest) else 50.0
