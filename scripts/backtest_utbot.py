import pandas as pd
import numpy as np
import vectorbt as vbt
from pathlib import Path
import glob
import json
from datetime import datetime

def load_data():
    files = glob.glob('/mnt/tick-storage/historical/equities/SPY/SPY_1D_*.parquet')
    if not files:
        raise ValueError("No data files found for SPY")
    dfs = []
    for f in files:
        df = pd.read_parquet(f)
        dfs.append(df)
    df = pd.concat(dfs)
    
    # standardize columns
    cols = [c.lower() for c in df.columns]
    df.columns = cols
    if 'ts' in df.columns:
        df['timestamp'] = pd.to_datetime(df['ts'])
        df = df.set_index('timestamp')
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
    elif df.index.name != 'timestamp' and type(df.index) == pd.DatetimeIndex:
        pass # use existing index
    
    df = df.sort_index()
    # Filter: 2020-01-01 to present
    df = df.loc['2020-01-01':]
    return df

def calculate_ut_signals(df, atr_period=14, sensitivity=1.0):
    # ATR calculation
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_period, adjust=False).mean()
    
    # Trailing stop
    trail_stop = pd.Series(index=df.index, dtype=float)
    trail_stop.iloc[0] = close.iloc[0]
    
    for i in range(1, len(close)):
        prev_stop = trail_stop.iloc[i-1]
        curr_close = close.iloc[i]
        curr_atr = atr.iloc[i] * sensitivity
        
        if curr_close > prev_stop:
            trail_stop.iloc[i] = max(prev_stop, curr_close - curr_atr)
        else:
            trail_stop.iloc[i] = min(prev_stop, curr_close + curr_atr)
    
    # Signals
    buy_sig = (close > trail_stop) & (close.shift() <= trail_stop.shift())
    sell_sig = (close < trail_stop) & (close.shift() >= trail_stop.shift())
    
    return buy_sig, sell_sig, trail_stop

def main():
    print("Loading SPY data...")
    df = load_data()
    print("Calculating signals...")
    entries, exits, trail = calculate_ut_signals(df)
    
    print("Running vectorbt backtest...")
    portfolio = vbt.Portfolio.from_signals(
        close=df['close'],
        entries=entries,
        exits=exits,
        init_cash=100000,
        fees=0.001,
        slippage=0.001,
        freq='1D'
    )
    
    total_return = portfolio.total_return()
    sharpe = portfolio.sharpe_ratio()
    max_dd = portfolio.max_drawdown()
    win_rate = portfolio.trades.win_rate()
    total_trades = portfolio.trades.count()
    avg_trade_duration = portfolio.trades.duration.mean()
    profit_factor = portfolio.trades.profit_factor()
    calmar = portfolio.calmar_ratio()
    
    if sharpe > 1.0 and abs(max_dd) < 0.20:
        status = "PASS"
    else:
        status = "FAIL"
        
    start_date = df.index.min().strftime('%Y-%m-%d')
    end_date = df.index.max().strftime('%Y-%m-%d')
    
    report = f"""═══════════════════════════════════════
UTBot Strategy Backtest — SPY Daily
Period: {start_date} to {end_date}
═══════════════════════════════════════
Total Return:    {total_return:.1%}
Sharpe Ratio:    {sharpe:.2f}
Max Drawdown:    {max_dd:.1%}
Win Rate:        {win_rate:.1%}
Total Trades:    {total_trades}
Profit Factor:   {profit_factor:.2f}
Calmar Ratio:    {calmar:.2f}
═══════════════════════════════════════
VERDICT: {status}"""
    print(report)
    
    results = {
        "strategy": "UTBot",
        "symbol": "SPY",
        "timeframe": "1D",
        "start_date": start_date,
        "end_date": end_date,
        "total_return": float(total_return) if not np.isnan(total_return) else 0.0,
        "sharpe_ratio": float(sharpe) if not np.isnan(sharpe) else 0.0,
        "max_drawdown": float(max_dd) if not np.isnan(max_dd) else 0.0,
        "win_rate": float(win_rate) if not np.isnan(win_rate) else 0.0,
        "total_trades": int(total_trades) if not np.isnan(total_trades) else 0,
        "profit_factor": float(profit_factor) if not np.isnan(profit_factor) else 0.0,
        "calmar_ratio": float(calmar) if not np.isnan(calmar) else 0.0,
        "status": status
    }
    
    out_dir = Path("/mnt/tick-storage/backtest_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "utbot_spy_daily.json", "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    main()
