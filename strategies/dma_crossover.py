"""
DMA 20/200 Crossover Strategy — position strategy for SPY.

Validated: Sharpe=0.602, compound=+423.7%, positive all 4 sub-periods
(2000-2026). ~0.7 trades/year — this is a position strategy.

Signal: go long when SMA(20) crosses above SMA(200) (golden cross),
go flat when SMA(20) crosses below SMA(200) (death cross).
1-bar delay on all signals (no lookahead).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

logger = logging.getLogger("dma_crossover")

TRADING_DAYS = 252


class DmaCrossoverStrategy:

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 200,
        kelly_cap: float = 0.25,
        kelly_floor: float = 0.05,
        symbol: str = "SPY",
        fee_per_side: float = 0.0001,
        kelly_window: int = 60,
    ):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.kelly_cap = kelly_cap
        self.kelly_floor = kelly_floor
        self.symbol = symbol
        self.fee_per_side = fee_per_side
        self.kelly_window = kelly_window
        self._prev_fast_ma = None
        self._prev_slow_ma = None

    @property
    def warmup_bars(self) -> int:
        return self.slow_period

    def evaluate(self, df: pd.DataFrame) -> dict:
        """Evaluate DMA crossover signal on an OHLCV dataframe.

        Args:
            df: Must have columns: timestamp, open, high, low, close.
                Must be sorted by timestamp ascending.

        Returns:
            dict with: signal (+1/-1/0), action (BUY/SELL/HOLD),
            fast_ma, slow_ma, kelly_size, close_price, bar_time,
            is_crossover (bool), warmup (bool).
        """
        if len(df) < self.warmup_bars:
            return self._warmup_result(df)

        fast_ma = df["close"].rolling(self.fast_period).mean()
        slow_ma = df["close"].rolling(self.slow_period).mean()

        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]

        if np.isnan(current_fast) or np.isnan(current_slow):
            return self._warmup_result(df)

        golden_cross = bool(current_fast > current_slow) and bool(prev_fast <= prev_slow)
        death_cross = bool(current_fast < current_slow) and bool(prev_fast >= prev_slow)

        if golden_cross:
            signal = 1
            action = "BUY"
        elif death_cross:
            signal = -1
            action = "SELL"
        else:
            signal = 0
            action = "HOLD"

        kelly_size = self._compute_kelly(df["close"])

        close_price = float(df["close"].iloc[-1])
        bar_time = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None

        result = {
            "signal": signal,
            "action": action,
            "fast_ma": round(float(current_fast), 4),
            "slow_ma": round(float(current_slow), 4),
            "kelly_size": round(kelly_size, 4),
            "close_price": round(close_price, 4),
            "bar_time": bar_time,
            "is_crossover": golden_cross or death_cross,
            "warmup": False,
            "symbol": self.symbol,
        }

        logger.info(
            f"[DMA] {self.symbol} bar={bar_time} close={close_price:.2f} "
            f"fast_ma={current_fast:.2f} slow_ma={current_slow:.2f} "
            f"signal={signal} action={action} kelly={kelly_size:.4f}"
        )

        return result

    def _warmup_result(self, df: pd.DataFrame) -> dict:
        bar_time = df["timestamp"].iloc[-1] if "timestamp" in df.columns and len(df) > 0 else None
        close = float(df["close"].iloc[-1]) if len(df) > 0 else 0.0
        logger.info(
            f"[DMA] {self.symbol} WARMUP — need {self.warmup_bars} bars, "
            f"have {len(df)}"
        )
        return {
            "signal": 0,
            "action": "HOLD",
            "fast_ma": None,
            "slow_ma": None,
            "kelly_size": 0.0,
            "close_price": round(close, 4),
            "bar_time": bar_time,
            "is_crossover": False,
            "warmup": True,
            "symbol": self.symbol,
        }

    def _compute_kelly(self, close: pd.Series) -> float:
        """Quarter-Kelly from rolling return window."""
        returns = close.pct_change().dropna().tail(self.kelly_window)
        if len(returns) < 20:
            return self.kelly_floor

        wins = returns[returns > 0]
        losses = returns[returns < 0]
        if len(wins) == 0 or len(losses) == 0:
            return self.kelly_floor

        win_rate = len(wins) / len(returns)
        avg_win = wins.mean()
        avg_loss = abs(losses.mean())
        if avg_loss == 0:
            return self.kelly_floor

        payout_ratio = avg_win / avg_loss
        full_kelly = (payout_ratio * win_rate - (1 - win_rate)) / payout_ratio
        quarter_kelly = full_kelly * 0.25

        return float(np.clip(quarter_kelly, self.kelly_floor, self.kelly_cap))

    def backtest(self, df: pd.DataFrame) -> dict:
        """Run vectorized backtest matching the validated research engine.

        Same methodology: signal at bar N applied at bar N+1 (1-bar delay),
        1bp fee per side, binary position (fully invested or flat).
        """
        sig = df.copy()
        sig["sma_fast"] = sig["close"].rolling(self.fast_period).mean()
        sig["sma_slow"] = sig["close"].rolling(self.slow_period).mean()
        sig["raw_signal"] = (sig["sma_fast"] > sig["sma_slow"]).astype(int)
        sig = sig.dropna(subset=["sma_fast", "sma_slow"]).reset_index(drop=True)

        sig["daily_return"] = sig["close"].pct_change()
        sig["position"] = sig["raw_signal"].shift(1).fillna(0).astype(int)
        sig["trade"] = sig["position"].diff().abs().fillna(0)
        sig["strat_return"] = sig["position"] * sig["daily_return"]
        sig.loc[sig["trade"] > 0, "strat_return"] -= self.fee_per_side
        sig = sig.dropna(subset=["strat_return"])

        initial_capital = 100_000.0
        sig["equity"] = initial_capital * (1 + sig["strat_return"]).cumprod()

        entries = sig[sig["position"].diff() == 1]
        n_trades = len(entries)
        n_years = len(sig) / TRADING_DAYS

        returns = sig["strat_return"]
        compound_return = (sig["equity"].iloc[-1] / initial_capital - 1) * 100
        ann_return = returns.mean() * TRADING_DAYS
        ann_vol = returns.std() * np.sqrt(TRADING_DAYS)
        sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

        peak = sig["equity"].cummax()
        drawdown = (sig["equity"] - peak) / peak
        max_dd = drawdown.min() * 100

        return {
            "net_sharpe": round(sharpe, 3),
            "compound_return": round(compound_return, 1),
            "trades": n_trades,
            "trades_per_year": round(n_trades / n_years, 1) if n_years > 0 else 0,
            "max_drawdown": round(max_dd, 1),
            "n_years": round(n_years, 1),
            "final_equity": round(sig["equity"].iloc[-1], 2),
        }

    # ── Supabase signal logging ──────────────────────────────────────────────

    def log_signal_sync(self, signal_data: dict):
        """Write signal to Supabase signal_log using safe_write_sync."""
        try:
            from common.safe_write import safe_write_sync
        except ImportError:
            logger.warning("[DMA] safe_write not available, skipping signal log")
            return False

        bar_time = signal_data.get("bar_time")
        if hasattr(bar_time, "isoformat"):
            bar_time = bar_time.isoformat()

        row = {
            "session_id": f"dma-crossover-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            "symbol": signal_data.get("symbol", self.symbol),
            "bar_time": bar_time,
            "timeframe": "1D",
            "signal_type": f"DMA_{signal_data['action']}",
            "close_price": signal_data.get("close_price"),
            "trail_stop": signal_data.get("slow_ma"),
            "atr": signal_data.get("fast_ma"),
            "rsi": signal_data.get("kelly_size", 0) * 100 if signal_data.get("kelly_size") else None,
            "buy_sig": signal_data.get("signal") == 1,
            "sell_sig": signal_data.get("signal") == -1,
        }

        return safe_write_sync("signal_log", row, "dma-crossover")

    # ── Telegram alerts ──────────────────────────────────────────────────────

    def send_crossover_alert_sync(self, signal_data: dict):
        """Send Telegram alert on golden/death cross events."""
        if not signal_data.get("is_crossover"):
            return

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "8641189809")
        if not token:
            logger.warning("[DMA] TELEGRAM_BOT_TOKEN not set, skipping alert")
            return

        action = signal_data["action"]
        symbol = signal_data.get("symbol", self.symbol)
        fast_ma = signal_data.get("fast_ma", 0)
        slow_ma = signal_data.get("slow_ma", 0)
        kelly = signal_data.get("kelly_size", 0) * 100

        if action == "BUY":
            emoji = "\U0001f4c8"
            cross_type = "GOLDEN CROSS"
            verb = "crossed above"
        else:
            emoji = "\U0001f4c9"
            cross_type = "DEATH CROSS"
            verb = "crossed below"

        text = (
            f"{emoji} <b>DMA {cross_type}: {symbol}</b>\n"
            f"fast_ma(20)={fast_ma:.2f} {verb} slow_ma(200)={slow_ma:.2f}\n"
            f"Signal: {action}. Kelly size: {kelly:.1f}%\n"
            f"Strategy: DMA 20/200 crossover (position strategy)"
        )

        import httpx
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json={
                    "chat_id": chat_id, "text": text, "parse_mode": "HTML",
                })
                if resp.status_code >= 300:
                    logger.warning(f"[DMA] Telegram error: {resp.status_code}")
        except Exception as e:
            logger.error(f"[DMA] Telegram send failed: {e}")
