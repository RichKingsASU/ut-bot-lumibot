import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import json
import os

def compute_ut_bot(df: pd.DataFrame, atr_period: int = 10, sensitivity: float = 1.0) -> pd.DataFrame:
    df['high_low'] = df['High'] - df['Low']
    df['high_close'] = abs(df['High'] - df['Close'].shift())
    df['low_close'] = abs(df['Low'] - df['Close'].shift())
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=atr_period).mean()

    df['loss'] = sensitivity * df['atr']
    df['trail_stop'] = 0.0

    for i in range(1, len(df)):
        close = df.iloc[i]['Close']
        prev_close = df.iloc[i-1]['Close']
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
        (df['Close'] > df['trail_stop']) &
        (df['Close'].shift() <= df['prev_trail_stop']),
        'signal'
    ] = 1
    df.loc[
        (df['Close'] < df['trail_stop']) &
        (df['Close'].shift() >= df['prev_trail_stop']),
        'signal'
    ] = -1

    return df

def run_backtest():
    print("Fetching SPY data (2010-present)...")
    ticker = yf.Ticker("SPY")
    df = ticker.history(start="2010-01-01", end=datetime.now().strftime("%Y-%m-%d"))
    
    print("Computing UT Bot...")
    df = compute_ut_bot(df, 10, 1.0)
    
    print("Simulating Trades (Next Open)...")
    # Simulation: Buy on next open after signal
    position = 0
    entry_price = 0.0
    trades = []
    
    for i in range(1, len(df)-1):
        sig = df.iloc[i]['signal']
        date = df.index[i+1] # Next day execution
        nxt_open = df.iloc[i+1]['Open']
        
        if position == 0 and sig != 0:
            position = sig
            entry_price = nxt_open
            entry_date = date
        elif position != 0 and sig != 0 and sig != position:
            # Reverse / close
            exit_price = nxt_open
            pnl = (exit_price - entry_price) / entry_price if position == 1 else (entry_price - exit_price) / entry_price
            trades.append({
                "entry_date": entry_date,
                "exit_date": date,
                "direction": "LONG" if position == 1 else "SHORT",
                "pnl_pct": pnl
            })
            # Reverse
            position = sig
            entry_price = nxt_open
            entry_date = date

    tdf = pd.DataFrame(trades)
    if tdf.empty:
        print("No trades found.")
        return
        
    wins = tdf[tdf['pnl_pct'] > 0]
    losses = tdf[tdf['pnl_pct'] <= 0]
    
    metrics = {
        "total_trades": len(tdf),
        "win_rate": len(wins) / len(tdf),
        "avg_winner": wins['pnl_pct'].mean() if len(wins) > 0 else 0,
        "avg_loser": losses['pnl_pct'].mean() if len(losses) > 0 else 0,
    }
    metrics["profit_factor"] = abs(wins['pnl_pct'].sum() / losses['pnl_pct'].sum()) if losses['pnl_pct'].sum() != 0 else float('inf')
    
    print("\n--- BASELINE METRICS ---")
    print(json.dumps(metrics, indent=2))
    
    os.makedirs("research/results", exist_ok=True)
    with open("research/results/baseline_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    tdf.to_csv("research/results/trades.csv", index=False)
    print("\nResults saved to research/results/")

if __name__ == "__main__":
    run_backtest()
