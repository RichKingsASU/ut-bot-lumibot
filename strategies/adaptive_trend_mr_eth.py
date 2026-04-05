# adaptive_trend_mr_eth.py
# Adaptive Trend + Mean Reversion Hybrid Strategy - ETH/USD
# Lumibot v4.4.56+ | Alpaca Crypto (24/7) | 15m bars
#
# REGIME DETECTION (ADX):
#   ADX > 25  -> Trend mode : EMA 9/21 crossover + ATR 2.5x trailing stop
#   ADX <= 25 -> MR mode    : BB(20,2) outer touch + RSI extreme confirmation
# SIZING: Kelly-inspired, capped at 25% portfolio. 2% risk per trade.
# STOPS: 3% hard SL, 6% TP (2:1 R:R) on every position.
# COOLDOWN: 3-bar pause after any exit to prevent churn.

from lumibot.strategies import Strategy
from lumibot.entities import Asset
import pandas as pd
import numpy as np


class AdaptiveTrendMR(Strategy):

    parameters = {
        "symbol": "ETH",
        "quote_symbol": "USD",
        "timeframe": "15m",
        "adx_period": 14,
        "adx_threshold": 25,
        "ema_fast": 9,
        "ema_slow": 21,
        "atr_period": 14,
        "atr_multiplier": 2.5,
        "bb_period": 20,
        "bb_std": 2.0,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "risk_per_trade": 0.02,
        "kelly_cap": 0.25,
        "sl_pct": 0.03,
        "tp_pct": 0.06,
        "cooldown_bars": 3,
    }

    def initialize(self):
        self.sleeptime = self.parameters["timeframe"]
        self.symbol = self.parameters["symbol"]
        self.quote_symbol = self.parameters["quote_symbol"]
        self.asset = Asset(symbol=self.symbol, asset_type="crypto")
        self.quote_asset = Asset(symbol=self.quote_symbol, asset_type="crypto")
        self.adx_period = self.parameters["adx_period"]
        self.adx_threshold = self.parameters["adx_threshold"]
        self.ema_fast = self.parameters["ema_fast"]
        self.ema_slow = self.parameters["ema_slow"]
        self.atr_period = self.parameters["atr_period"]
        self.atr_mult = self.parameters["atr_multiplier"]
        self.bb_period = self.parameters["bb_period"]
        self.bb_std = self.parameters["bb_std"]
        self.rsi_period = self.parameters["rsi_period"]
        self.rsi_os = self.parameters["rsi_oversold"]
        self.rsi_ob = self.parameters["rsi_overbought"]
        self.risk_pct = self.parameters["risk_per_trade"]
        self.kelly_cap = self.parameters["kelly_cap"]
        self.sl_pct = self.parameters["sl_pct"]
        self.tp_pct = self.parameters["tp_pct"]
        self.cooldown_bars = self.parameters["cooldown_bars"]
        self._cooldown_counter = 0
        self._trail_stop = None
        self._entry_price = None
        self._position_side = None
        self._min_bars = max(self.ema_slow, self.bb_period,
                             self.rsi_period, self.adx_period) + 5

    def on_trading_iteration(self):
        if self._cooldown_counter > 0:
            self._cooldown_counter -= 1
            return
        lookback = self._min_bars + 10
        bars = self.get_historical_prices(
            self.asset, lookback, "minute",
            timeframe_multiplier=15, quote=self.quote_asset
        )
        if bars is None or bars.df is None or len(bars.df) < self._min_bars:
            return
        df = bars.df.copy()
        df = self._compute_indicators(df)
        row = df.iloc[-1]
        prev = df.iloc[-2]
        position = self.get_position(self.asset)
        if position and position.quantity != 0:
            self._manage_position(row, position)
            return
        if row["adx"] > self.adx_threshold:
            self._trend_entry(row, prev)
        else:
            self._mr_entry(row, prev)

    def _compute_indicators(self, df):
        high = df["high"]
        low = df["low"]
        close = df["close"]
        df["ema_fast"] = close.ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = close.ewm(span=self.ema_slow, adjust=False).mean()
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=self.atr_period, adjust=False).mean()
        df = self._add_adx(df)
        df["bb_mid"] = close.rolling(self.bb_period).mean()
        df["bb_std_v"] = close.rolling(self.bb_period).std()
        df["bb_upper"] = df["bb_mid"] + self.bb_std * df["bb_std_v"]
        df["bb_lower"] = df["bb_mid"] - self.bb_std * df["bb_std_v"]
        df["rsi"] = self._calc_rsi(close, self.rsi_period)
        return df

    def _add_adx(self, df):
        high = df["high"]
        low = df["low"]
        close = df["close"]
        n = self.adx_period
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = np.where(
            (up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where(
            (down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr_s = pd.Series(tr.values).ewm(span=n, adjust=False).mean()
        plus_di = (100 * pd.Series(plus_dm).ewm(span=n, adjust=False).mean()
                   / atr_s)
        minus_di = (100 * pd.Series(minus_dm).ewm(span=n, adjust=False).mean()
                    / atr_s)
        dx = (100 * (plus_di - minus_di).abs()
              / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
        df["adx"] = dx.ewm(span=n, adjust=False).mean().values
        df["plus_di"] = plus_di.values
        df["minus_di"] = minus_di.values
        return df

    @staticmethod
    def _calc_rsi(series, period):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_g = gain.ewm(com=period - 1, adjust=False).mean()
        avg_l = loss.ewm(com=period - 1, adjust=False).mean()
        rs = avg_g / avg_l.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _trend_entry(self, row, prev):
        long_cross = (prev["ema_fast"] <= prev["ema_slow"]
                      and row["ema_fast"] > row["ema_slow"])
        short_cross = (prev["ema_fast"] >= prev["ema_slow"]
                       and row["ema_fast"] < row["ema_slow"])
        di_long = row["plus_di"] > row["minus_di"]
        di_short = row["minus_di"] > row["plus_di"]
        price = row["close"]
        atr = row["atr"]
        if long_cross and di_long:
            sl = price - self.sl_pct * price
            tp = price + self.tp_pct * price
            qty = self._size_position(price, price - sl)
            if qty > 0:
                self._submit_entry("buy", qty, price, sl, tp, "trend_long")
                self._trail_stop = price - self.atr_mult * atr
                self._position_side = "long"
        elif short_cross and di_short:
            sl = price + self.sl_pct * price
            tp = price - self.tp_pct * price
            qty = self._size_position(price, sl - price)
            if qty > 0:
                self._submit_entry("sell", qty, price, sl, tp, "trend_short")
                self._trail_stop = price + self.atr_mult * atr
                self._position_side = "short"

    def _mr_entry(self, row, prev):
        price = row["close"]
        long_signal = (price < row["bb_lower"]) and (row["rsi"] < self.rsi_os)
        short_signal = (price > row["bb_upper"]) and (row["rsi"] > self.rsi_ob)
        if long_signal:
            sl = price - self.sl_pct * price
            tp = row["bb_mid"]
            if tp <= price:
                tp = price + self.tp_pct * price
            qty = self._size_position(price, price - sl)
            if qty > 0:
                self._submit_entry("buy", qty, price, sl, tp, "mr_long")
                self._position_side = "long"
        elif short_signal:
            sl = price + self.sl_pct * price
            tp = row["bb_mid"]
            if tp >= price:
                tp = price - self.tp_pct * price
            qty = self._size_position(price, sl - price)
            if qty > 0:
                self._submit_entry("sell", qty, price, sl, tp, "mr_short")
                self._position_side = "short"

    def _manage_position(self, row, position):
        if self._position_side is None or self._trail_stop is None:
            return
        price = row["close"]
        atr = row["atr"]
        if self._position_side == "long":
            new_trail = price - self.atr_mult * atr
            if new_trail > self._trail_stop:
                self._trail_stop = new_trail
            if price <= self._trail_stop:
                self.sell_all()
                self._reset_state()
        elif self._position_side == "short":
            new_trail = price + self.atr_mult * atr
            if new_trail < self._trail_stop:
                self._trail_stop = new_trail
            if price >= self._trail_stop:
                self.sell_all()
                self._reset_state()

    def _size_position(self, price, risk_per_unit):
        equity = self.get_portfolio_value()
        if equity <= 0 or risk_per_unit <= 0 or price <= 0:
            return 0.0
        risk_qty = (equity * self.risk_pct) / risk_per_unit
        kelly_qty = (equity * self.kelly_cap) / price
        return round(min(risk_qty, kelly_qty), 6)

    def _submit_entry(self, side, qty, price, sl, tp, tag):
        order = self.create_order(
            self.asset, quantity=qty, side=side,
            type="market", quote=self.quote_asset
        )
        self.submit_order(order)
        self._entry_price = price
        self.log_message(
            f"[{tag}] {side.upper()} {qty:.4f} ETH @ ~{price:.2f} "
            f"| SL={sl:.2f} TP={tp:.2f}"
        )

    def _reset_state(self):
        self._trail_stop = None
        self._entry_price = None
        self._position_side = None
        self._cooldown_counter = self.cooldown_bars

    def on_filled_order(self, position, order, price, quantity, multiplier):
        self.log_message(
            f"Order filled: {order.side} {quantity:.4f} ETH @ {price:.2f}")

    def on_canceled_order(self, order):
        self.log_message(f"Order canceled: {order}")
