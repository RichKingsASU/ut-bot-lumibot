#!/usr/bin/env python3
"""
QuestDB high-frequency spot backtester.
Queries raw tick data from QuestDB, resamples it to generate signals,
and runs a simulated tick-by-tick execution.

Usage:
  python3 scripts/backtest_questdb_spot.py --symbol BTCUSD --start 2026-05-24 --end 2026-05-25
"""

import argparse
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("QuestDBSpotBacktester")

def _date(s: str) -> date:
    return date.fromisoformat(s)

def fetch_raw_ticks(symbol: str, start: date, end: date, questdb_url: str) -> pd.DataFrame:
    """Fetch raw ticks from QuestDB ticks table."""
    symbol_clean = symbol.replace("/", "")
    start_str = f"{start.isoformat()}T00:00:00.000000Z"
    end_str = f"{end.isoformat()}T23:59:59.999999Z"

    query = f"""
    SELECT timestamp, price, size
    FROM ticks
    WHERE symbol = '{symbol_clean}'
      AND timestamp >= '{start_str}'
      AND timestamp <= '{end_str}'
    ORDER BY timestamp;
    """
    log.info(f"Querying QuestDB ticks for {symbol_clean} from {start} to {end}...")
    url = f"{questdb_url}/exec"
    resp = requests.get(url, params={"query": query.strip()}, timeout=30.0)
    if resp.status_code != 200:
        raise RuntimeError(f"QuestDB query failed with status code {resp.status_code}: {resp.text}")
    
    data = resp.json()
    if "dataset" not in data or not data["dataset"]:
        return pd.DataFrame()
        
    cols = [col["name"] for col in data["columns"]]
    df = pd.DataFrame(data["dataset"], columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    return df

def calculate_ut_signals(df_1m, atr_period=10, sensitivity=1.0):
    """Calculate UT Bot ATR signals on 1m bars."""
    high = df_1m["high"]
    low = df_1m["low"]
    close = df_1m["close"]
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(window=atr_period, min_periods=1).mean()
    
    trail_stop = pd.Series(index=df_1m.index, dtype=float)
    trail_stop.iloc[0] = close.iloc[0]
    
    for i in range(1, len(close)):
        prev_stop = trail_stop.iloc[i-1]
        curr_close = close.iloc[i]
        curr_atr = atr.iloc[i] * sensitivity
        
        if curr_close > prev_stop:
            trail_stop.iloc[i] = max(prev_stop, curr_close - curr_atr)
        else:
            trail_stop.iloc[i] = min(prev_stop, curr_close + curr_atr)
            
    buy_sig = (close > trail_stop) & (close.shift() <= trail_stop.shift())
    sell_sig = (close < trail_stop) & (close.shift() >= trail_stop.shift())
    
    return buy_sig, sell_sig

def run_simulation(df_ticks, buy_signals, sell_signals, init_cash=100000.0, fees_pct=0.001, slippage_pct=0.0005):
    """Simulate tick-by-tick executions based on 1m signals."""
    cash = init_cash
    position = 0.0  # units of asset
    trades = []
    equity_curve = []
    
    # Track the active trade
    entry_price = 0.0
    entry_time = None
    
    # We execute at the first tick of the next minute bar
    signal_minutes = set()
    active_signal = None  # "BUY" | "SELL" | None
    
    # Map 1m signals
    buy_times = set(buy_signals[buy_signals].index)
    sell_times = set(sell_signals[sell_signals].index)
    
    log.info("Running tick-by-tick simulator loop...")
    
    for ts, row in df_ticks.iterrows():
        price = float(row["price"])
        size = float(row["size"])
        
        # Check if we crossed a minute boundary where a signal is active
        # We check the floor of the timestamp (to the minute)
        ts_min = ts.floor("1min")
        
        # If there was a buy signal at the previous minute and we are now in the next minute
        if active_signal == "BUY" and position == 0.0:
            # Buy fill: entry at tick price + slippage
            fill_price = price * (1.0 + slippage_pct)
            commission = cash * fees_pct
            capital_after_fees = cash - commission
            position = capital_after_fees / fill_price
            cash = 0.0
            entry_price = fill_price
            entry_time = ts
            trades.append({
                "type": "BUY",
                "time": ts.isoformat(),
                "price": fill_price,
                "size": position,
                "commission": commission
            })
            active_signal = None
            log.info(f"Executed BUY at {ts} | Price: {fill_price:.4f} | Size: {position:.6f}")
            
        elif active_signal == "SELL" and position > 0.0:
            # Sell fill: exit at tick price - slippage
            fill_price = price * (1.0 - slippage_pct)
            gross_value = position * fill_price
            commission = gross_value * fees_pct
            net_value = gross_value - commission
            cash = net_value
            pnl = net_value - (position * entry_price)
            pnl_pct = (fill_price - entry_price) / entry_price
            
            trades.append({
                "type": "SELL",
                "time": ts.isoformat(),
                "price": fill_price,
                "size": position,
                "commission": commission,
                "net_pnl": pnl,
                "pnl_pct": pnl_pct,
                "duration_sec": (ts - entry_time).total_seconds()
            })
            position = 0.0
            active_signal = None
            log.info(f"Executed SELL at {ts} | Price: {fill_price:.4f} | PnL: ${pnl:.2f} ({pnl_pct:.2%})")
            
        # Update signal status based on 1m bars
        # A signal generated at bar index `t` is available at the start of the next minute bar `t+1`
        if ts_min in buy_times and active_signal is None and position == 0.0:
            active_signal = "BUY"
        elif ts_min in sell_times and active_signal is None and position > 0.0:
            active_signal = "SELL"
            
        # Record equity point (cash + market value of position)
        equity = cash + (position * price)
        equity_curve.append((ts, equity))
        
    # Flatten at the very last tick if in position
    if position > 0.0:
        last_ts = df_ticks.index[-1]
        last_price = float(df_ticks.iloc[-1]["price"])
        fill_price = last_price * (1.0 - slippage_pct)
        gross_value = position * fill_price
        commission = gross_value * fees_pct
        net_value = gross_value - commission
        cash = net_value
        pnl = net_value - (position * entry_price)
        pnl_pct = (fill_price - entry_price) / entry_price
        trades.append({
            "type": "SELL_FLATTEN",
            "time": last_ts.isoformat(),
            "price": fill_price,
            "size": position,
            "commission": commission,
            "net_pnl": pnl,
            "pnl_pct": pnl_pct,
            "duration_sec": (last_ts - entry_time).total_seconds()
        })
        position = 0.0
        log.info(f"Executed EOD FLATTEN at {last_ts} | Price: {fill_price:.4f} | PnL: ${pnl:.2f}")

    eq_df = pd.DataFrame(equity_curve, columns=["timestamp", "equity"]).set_index("timestamp")
    return trades, eq_df

def compute_metrics(init_cash, trades, eq_df):
    """Calculate key performance statistics."""
    total_trades = len(trades)
    if total_trades == 0:
        return {}
        
    final_equity = eq_df["equity"].iloc[-1]
    total_return = (final_equity - init_cash) / init_cash
    
    # Extract exits
    exits = [t for t in trades if t["type"] in ["SELL", "SELL_FLATTEN"]]
    if not exits:
        return {"total_return": total_return, "trades_count": 0}
        
    win_trades = [e for e in exits if e.get("net_pnl", 0) > 0]
    win_rate = len(win_trades) / len(exits)
    
    gross_profits = sum(e["net_pnl"] for e in exits if e["net_pnl"] > 0)
    gross_losses = abs(sum(e["net_pnl"] for e in exits if e["net_pnl"] < 0))
    profit_factor = gross_profits / gross_losses if gross_losses > 0 else float("inf")
    
    # Sharpe ratio (from daily resampled equity)
    eq_daily = eq_df["equity"].resample("1D").last().dropna()
    if len(eq_daily) > 2:
        daily_returns = eq_daily.pct_change().dropna()
        std = daily_returns.std()
        mean = daily_returns.mean()
        sharpe = (mean / std) * np.sqrt(252) if std > 0 else 0.0
    else:
        sharpe = 0.0
        
    # Drawdown
    cum_max = eq_df["equity"].cummax()
    drawdowns = (eq_df["equity"] - cum_max) / cum_max
    max_dd = drawdowns.min()
    
    return {
        "total_return": float(total_return),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
        "total_trades": len(exits),
        "profit_factor": float(profit_factor),
        "final_equity": float(final_equity)
    }

def main():
    p = argparse.ArgumentParser(description="QuestDB High-Frequency Spot Backtester")
    p.add_argument("--symbol", default="BTCUSD")
    p.add_argument("--start", type=_date, default=date(2026, 5, 24))
    p.add_argument("--end", type=_date, default=date(2026, 5, 25))
    p.add_argument("--questdb-url", default="http://localhost:9000", dest="questdb_url")
    p.add_argument("--atr-period", type=int, default=10, dest="atr_period")
    p.add_argument("--sensitivity", type=float, default=1.0, dest="sensitivity")
    p.add_argument("--init-cash", type=float, default=100000.0, dest="init_cash")
    p.add_argument("--fees-pct", type=float, default=0.001, dest="fees_pct")
    p.add_argument("--slippage-pct", type=float, default=0.0005, dest="slippage_pct")
    args = p.parse_args()
    
    # 1. Fetch raw ticks
    try:
        df_ticks = fetch_raw_ticks(args.symbol, args.start, args.end, args.questdb_url)
    except Exception as e:
        log.error(f"Failed to fetch tick data: {e}")
        return 1
        
    if df_ticks.empty:
        log.warning("No ticks returned from QuestDB for the specified parameters.")
        return 0
        
    log.info(f"Loaded {len(df_ticks):,} ticks from QuestDB.")
    
    # 2. Resample ticks into 1-minute bars to generate signals
    log.info("Resampling ticks to 1-minute OHLCV bars...")
    df_1m = df_ticks["price"].resample("1min").ohlc()
    df_1m["volume"] = df_ticks["size"].resample("1min").sum()
    df_1m = df_1m.dropna()
    
    # 3. Calculate indicators
    log.info("Calculating UTBot signals...")
    buy_signals, sell_signals = calculate_ut_signals(df_1m, args.atr_period, args.sensitivity)
    
    # 4. Run tick-by-tick simulation
    trades, eq_df = run_simulation(
        df_ticks, buy_signals, sell_signals,
        init_cash=args.init_cash, fees_pct=args.fees_pct, slippage_pct=args.slippage_pct
    )
    
    # 5. Compute metrics
    metrics = compute_metrics(args.init_cash, trades, eq_df)
    
    # Print results
    report = f"""═══════════════════════════════════════
QuestDB HF Spot Backtest — {args.symbol}
Period: {args.start} to {args.end}
═══════════════════════════════════════
Total Return:    {metrics.get('total_return', 0.0):.1%}
Sharpe Ratio:    {metrics.get('sharpe_ratio', 0.0):.2f}
Max Drawdown:    {metrics.get('max_drawdown', 0.0):.1%}
Win Rate:        {metrics.get('win_rate', 0.0):.1%}
Total Trades:    {metrics.get('total_trades', 0)}
Profit Factor:   {metrics.get('profit_factor', 0.0):.2f}
Final Equity:    ${metrics.get('final_equity', args.init_cash):,.2f}
═══════════════════════════════════════"""
    print(report)
    
    # Save results
    results = {
        "strategy": "UTBot_Spot_HF",
        "symbol": args.symbol,
        "start": args.start.isoformat(),
        "end": args.end.isoformat(),
        "metrics": metrics,
        "trades_count": len(trades),
        "trades": trades
    }
    
    # Try /mnt/tick-storage/backtest_results first, fallback to backtests/results
    written = False
    try:
        out_dir = Path("/mnt/tick-storage/backtest_results")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"questdb_spot_{args.symbol}.json"
        with open(out_file, "w") as f:
            json.dump(results, f, indent=4)
        log.info(f"Saved backtest results to: {out_file}")
        written = True
    except Exception:
        pass

    if not written:
        out_dir = Path("backtests/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"questdb_spot_{args.symbol}.json"
        with open(out_file, "w") as f:
            json.dump(results, f, indent=4)
        log.info(f"Saved backtest results to: {out_file} (fallback)")
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
