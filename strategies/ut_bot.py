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
    get_daily_realized_pnl,
    get_daily_trade_count,
)
import adapters.supabase_logger as db
import config

logger = logging.getLogger("ut_bot_strategy")
ET = pytz.timezone("America/New_York")


from logger import bot_logger, ErrorCategory

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
        self.daily_realized_pnl = get_daily_realized_pnl()
        self.trades_today = get_daily_trade_count()
        bot_logger.info(f"Strategy Initialized. Symbol: {self.parameters['symbol']}, P&L: ${self.daily_realized_pnl:.2f}, Trades: {self.trades_today}/{config.MAX_TRADES_PER_DAY}", category=ErrorCategory.STRATEGY)

    def on_trading_iteration(self):
        # ── [RISK FIX] Check daily loss limit ─────────────────────────────
        if self.daily_realized_pnl <= -config.MAX_DAILY_LOSS:
            if not has_open_position():
                bot_logger.error(f"CRITICAL: DAILY LOSS LIMIT REACHED (${self.daily_realized_pnl:.2f}) — Trading suspended.", category=ErrorCategory.RISK)
                return
            else:
                bot_logger.warning(f"WARNING: DAILY LOSS LIMIT REACHED (${self.daily_realized_pnl:.2f}) — Managing existing position only.", category=ErrorCategory.RISK)

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

        # ── [DATA FRESHNESS GUARD] Check if last bar is stale ────────────────
        if not df.empty:
            last_bar_time = df.index[-1]
            now = datetime.now(last_bar_time.tzinfo if last_bar_time.tzinfo else ET)
            time_diff = (now - last_bar_time).total_seconds()
            
            # If data is > 90 seconds old, it's considered stale for 1m intraday trading
            if time_diff > 90:
                logger.error("STALE DATA DETECTED: Last bar (%s) is %.1f seconds old. Aborting iteration to prevent bad fills.", 
                             last_bar_time.strftime("%H:%M:%S"), time_diff)
                return
        else:
            logger.warning("Empty dataframe returned from broker. Aborting iteration.")
            return

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
        current_atr = df.iloc[-1]['atr'] if not pd.isna(df.iloc[-1]['atr']) else 0.0
        current_trail_stop = df.iloc[-1]['trail_stop']

        # ── Log the latest bar to Supabase (fire-and-forget) ─────────────
        try:
            last_bar = df.iloc[-1]
            db.log_bar(symbol, {
                "t": last_bar.name.isoformat() if hasattr(last_bar.name, "isoformat") else str(last_bar.name),
                "o": last_bar["open"], "h": last_bar["high"],
                "l": last_bar["low"],  "c": last_bar["close"],
                "v": int(last_bar.get("volume", 0)) if "volume" in last_bar.index else 0,
            })
        except Exception as e:
            logger.warning("[SUPABASE] bar_log write failed: %s", e)

        # ── Compute 5-minute RSI for exit logic ──────────────────────────
        current_rsi = self._compute_rsi(df['close'], self.parameters["rsi_period"])

        # ── Log signal to Supabase if a signal fired ─────────────────────
        if current_signal != 0:
            try:
                bar_time = df.index[-1]
                db.log_signal(
                    symbol=symbol,
                    bar_time=bar_time.isoformat() if hasattr(bar_time, "isoformat") else str(bar_time),
                    timeframe=self.parameters.get("timeframe", "1D"),
                    signal_type="UT_BUY" if current_signal == 1 else "UT_SELL",
                    close_price=float(current_price),
                    trail_stop=float(current_trail_stop),
                    atr=float(current_atr),
                    rsi=float(current_rsi),
                    buy_sig=(current_signal == 1),
                    sell_sig=(current_signal == -1),
                )
            except Exception as e:
                logger.warning("[SUPABASE] signal_log write failed: %s", e)

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
                order = sell_to_close(exit_reason=exit_reason)
                if order:
                    # Update local P&L tracker
                    trade_pnl = float(order.get("trade_pnl", 0))
                    self.daily_realized_pnl += trade_pnl
                    logger.info("Trade closed. Realized P&L: $%.2f | Day Total: $%.2f", trade_pnl, self.daily_realized_pnl)
                return

        # ── ENTRY LOGIC (if no open position) ───────────────────────────
        if not has_open_position() and current_signal != 0:
            # ── [RISK FIX] Check daily trade limit ─────────────────────────────
            if self.trades_today >= config.MAX_TRADES_PER_DAY:
                logger.warning("MAX_TRADES_PER_DAY (%d) reached. Entry blocked to prevent runaway.", 
                               config.MAX_TRADES_PER_DAY)
                return

            direction = "LONG" if current_signal == 1 else "SHORT"
            signal_label = "CALL" if direction == "LONG" else "PUT"
            qty = self.parameters.get("max_contracts", 1)
            
            # ── [RISK FIX] Check max position size ─────────────────────────────
            if qty > config.MAX_POSITION_SIZE:
                logger.warning("Requested qty %d exceeds MAX_POSITION_SIZE %d. Capping to limit.", 
                               qty, config.MAX_POSITION_SIZE)
                qty = config.MAX_POSITION_SIZE

            logger.info("SIGNAL DETECTED: %s %d contracts of %s", direction, qty, symbol)
            res = buy_to_open(
                underlying=symbol,
                direction=direction,
                qty=qty,
                underlying_price=float(current_price),
                current_rsi=current_rsi,
            )
            if res:
                self.trades_today += 1
                set_last_signal(signal_label)
            else:
                logger.error("Entry failed for %s. Trade count not incremented.", symbol)

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
