"""
K2 ATR Trailing Stop Strategy — Lumibot Implementation.

Signal logic:
  - K2 ATR trailing stop generates direction flips (+1 / -1)
  - RSI filter suppresses overbought buys and oversold sells
  - Entry: market order for shares (95% of cash)
  - Exit: market order to sell all shares
  - EOD flatten at 15:55 ET

Parameters are loaded from Supabase bot_config table and refreshed every
5 iterations (~5 minutes at 1M sleeptime).
"""

import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd
import pytz
from lumibot.strategies.strategy import Strategy

import adapters.supabase_logger as db

logger = logging.getLogger("ut_bot_strategy")
ET = pytz.timezone("America/New_York")


# ── K2 ATR Trailing Stop Engine ───────────────────────────────────────────────

def compute_atr(highs, lows, closes, period):
    import numpy as np
    n = len(closes)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
    tr[0] = highs[0] - lows[0]
    atr = np.zeros(n)
    atr[period-1] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i-1]*(period-1)+tr[i])/period
    return atr

def compute_k2_trailing_stop(closes, highs, lows, atr_period, atr_mult):
    import numpy as np
    n = len(closes)
    atr = compute_atr(highs, lows, closes, atr_period)
    stop = np.zeros(n)
    direction = np.zeros(n)
    stop[0] = closes[0]
    direction[0] = 1.0
    for i in range(1, n):
        loss = atr_mult * atr[i]
        c = closes[i]
        ps = stop[i-1]
        if c > ps:   stop[i] = max(ps, c - loss)
        elif c < ps: stop[i] = min(ps, c + loss)
        else:        stop[i] = ps
        direction[i] = 1.0 if c > stop[i] else -1.0
    return stop, direction


class UTBotStrategy(Strategy):
    # ── Default parameters (overridden by bot_config from Supabase) ───────
    ATR_PERIOD = 10
    ATR_MULT = 1.0
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70

    parameters = {
        "symbol": "IWM",
        "eod_flatten_time": "15:55",
    }

    def initialize(self):
        self.sleeptime = "1M"
        self.last_direction = None
        self._iteration_count = 0
        self._reload_config()

    # ── Supabase bot_config reload ────────────────────────────────────────

    def _reload_config(self):
        """Fetch bot_config rows from Supabase and update instance variables."""
        supa_url = os.getenv("SUPABASE_URL")
        supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not supa_url or not supa_key:
            logger.warning("[CONFIG] Supabase credentials not set — using defaults")
            return

        try:
            import httpx
            resp = httpx.get(
                f"{supa_url}/rest/v1/bot_config?select=key,value",
                headers={
                    "apikey": supa_key,
                    "Authorization": f"Bearer {supa_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("[CONFIG] bot_config fetch failed (%d): %s",
                               resp.status_code, resp.text[:200])
                return

            rows = resp.json()
            config = {row["key"]: row["value"] for row in rows}

            # Update active symbol
            if "active_symbol" in config:
                self.parameters["symbol"] = config["active_symbol"]

            # Update signal parameters
            if "atr_period" in config:
                self.ATR_PERIOD = int(config["atr_period"])
            if "atr_mult" in config:
                self.ATR_MULT = float(config["atr_mult"])
            if "rsi_period" in config:
                self.RSI_PERIOD = int(config["rsi_period"])
            if "rsi_oversold" in config:
                self.RSI_OVERSOLD = int(config["rsi_oversold"])
            if "rsi_overbought" in config:
                self.RSI_OVERBOUGHT = int(config["rsi_overbought"])

            # Update paper mode
            if "paper_mode" in config:
                is_paper = config["paper_mode"].lower() == "true"
                # Store for reference; broker config is set at startup
                self._paper_mode = is_paper

            logger.info("[CONFIG] Reloaded: symbol=%s ATR(%d, %.1f) RSI(%d, %d/%d)",
                        self.parameters["symbol"], self.ATR_PERIOD, self.ATR_MULT,
                        self.RSI_PERIOD, self.RSI_OVERSOLD, self.RSI_OVERBOUGHT)

        except Exception as e:
            logger.warning("[CONFIG] Failed to reload bot_config: %s", e)

    def on_trading_iteration(self):
        self._iteration_count += 1

        # Reload config every 5th iteration (~5 minutes)
        if self._iteration_count % 5 == 0:
            self._reload_config()

        symbol = self.parameters["symbol"]
        atr_period = self.ATR_PERIOD
        atr_mult = self.ATR_MULT

        # ── Check EOD flatten FIRST (highest priority) ───────────────────
        now_et = datetime.now(ET)
        flatten_h, flatten_m = map(int,
            self.parameters["eod_flatten_time"].split(":"))
        if now_et.hour > flatten_h or (
            now_et.hour == flatten_h and now_et.minute >= flatten_m
        ):
            positions = self.get_positions()
            if positions:
                logger.info("EOD flatten triggered at %s ET", now_et.strftime("%H:%M"))
                self.sell_all()
                return

        # ── Fetch historical prices ──────────────────────────────────────
        bars = self.get_historical_prices(symbol, 100, "day")
        df = bars.df

        # ══════════════════════════════════════════════════════════════════
        # K2 ATR TRAILING STOP SIGNAL ENGINE
        # ══════════════════════════════════════════════════════════════════

        closes = df["close"].values.astype(float)
        highs = df["high"].values.astype(float)
        lows = df["low"].values.astype(float)

        trail_stop, direction = compute_k2_trailing_stop(
            closes, highs, lows, atr_period, atr_mult
        )

        # Detect direction flip on the latest closed bar
        buy_signal = False
        sell_signal = False
        if len(direction) >= 2:
            prev_dir = direction[-2]
            curr_dir = direction[-1]
            if prev_dir == -1.0 and curr_dir == 1.0:
                buy_signal = True
            elif prev_dir == 1.0 and curr_dir == -1.0:
                sell_signal = True

        # ══════════════════════════════════════════════════════════════════
        # END SIGNAL ENGINE
        # ══════════════════════════════════════════════════════════════════

        current_price = closes[-1]
        current_trail_stop = trail_stop[-1]
        current_direction = direction[-1]

        # ── Compute RSI ──────────────────────────────────────────────────
        current_rsi = self._compute_rsi(df["close"], self.RSI_PERIOD)

        # ── RSI suppression ──────────────────────────────────────────────
        if buy_signal and current_rsi > self.RSI_OVERBOUGHT:
            logger.info("BUY suppressed — RSI %.1f > %d", current_rsi, self.RSI_OVERBOUGHT)
            buy_signal = False
        if sell_signal and current_rsi < self.RSI_OVERSOLD:
            logger.info("SELL suppressed — RSI %.1f < %d", current_rsi, self.RSI_OVERSOLD)
            sell_signal = False

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

        # ── Log signal to Supabase if a signal fired ─────────────────────
        if buy_signal or sell_signal:
            try:
                bar_time = df.index[-1]
                atr_vals = compute_atr(highs, lows, closes, atr_period)
                current_atr = float(atr_vals[-1])
                db.log_signal(
                    symbol=symbol,
                    bar_time=bar_time.isoformat() if hasattr(bar_time, "isoformat") else str(bar_time),
                    timeframe="1D",
                    signal_type="UT_BUY" if buy_signal else "UT_SELL",
                    close_price=float(current_price),
                    trail_stop=float(current_trail_stop),
                    atr=current_atr,
                    rsi=float(current_rsi),
                    buy_sig=buy_signal,
                    sell_sig=sell_signal,
                )
            except Exception as e:
                logger.warning("[SUPABASE] signal_log write failed: %s", e)

        # ── Determine position qty ────────────────────────────────────────
        positions = self.get_positions()
        qty = 0
        for pos in positions:
            if pos.symbol == symbol:
                qty = pos.quantity

        # ── Log line (preserve required format) ──────────────────────────
        self.log_message(
            f"Price: {current_price:.2f} | Trail Stop: {current_trail_stop:.2f} | "
            f"Dir: {current_direction:.0f} | RSI: {current_rsi:.1f} | Position: {qty}"
        )

        # ── SELL signal: sell all shares of active symbol ─────────────────
        if sell_signal and qty > 0:
            logger.info("SELL signal: selling %d shares of %s at %.2f",
                        qty, symbol, current_price)
            order = self.create_order(symbol, qty, "sell")
            self.submit_order(order)
            return

        # ── BUY signal: buy shares with 95% of cash ──────────────────────
        if buy_signal and qty == 0:
            cash = self.get_cash()
            shares_to_buy = int((cash * 0.95) / current_price)
            if shares_to_buy > 0:
                logger.info("BUY signal: buying %d shares of %s at %.2f (cash=%.2f)",
                            shares_to_buy, symbol, current_price, cash)
                order = self.create_order(symbol, shares_to_buy, "buy")
                self.submit_order(order)

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
