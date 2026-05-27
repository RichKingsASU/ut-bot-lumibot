import pandas as pd
import numpy as np
import vectorbt as vbt
from pathlib import Path
import glob
import json

def load_data():
    files = glob.glob('/mnt/tick-storage/historical/crypto/ETHUSD/ETHUSD_1m_*.parquet')
    if not files:
        raise ValueError("No data files found for ETHUSD")
    dfs = []
    for f in files:
        df = pd.read_parquet(f)
        dfs.append(df)
    df = pd.concat(dfs)
    
    cols = [c.lower() for c in df.columns]
    df.columns = cols
    if 'ts' in df.columns:
        df['timestamp'] = pd.to_datetime(df['ts'])
        df = df.set_index('timestamp')
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
    df = df.sort_index()
    df = df.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    # Filter 2022-01-01 to present
    df = df.loc['2022-01-01':]
    return df

def calculate_adaptive_signals(df, fast=8, slow=21, rsi_period=14, rsi_oversold=35, rsi_overbought=65):
    close = df['close']
    
    # EMAs
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    
    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(span=rsi_period).mean()
    loss = (-delta.clip(upper=0)).ewm(span=rsi_period).mean()
    rs = gain / loss.replace(0, np.inf)
    rsi = 100 - (100 / (1 + rs))
    
    # Trend filter
    trend_up = ema_fast > ema_slow
    trend_down = ema_fast < ema_slow
    
    # Mean reversion entries
    buy_sig = trend_up & (rsi < rsi_oversold)
    sell_sig = trend_down & (rsi > rsi_overbought)
    
    return buy_sig, sell_sig

def main():
    print("Loading ETHUSD 1m data and resampling to 15m...")
    df = load_data()
    print("Calculating AdaptiveTrendMR signals...")
    entries, exits = calculate_adaptive_signals(df)
    
    print("Running vectorbt backtest...")
    portfolio = vbt.Portfolio.from_signals(
        close=df['close'],
        entries=entries,
        exits=exits,
        init_cash=50000,
        fees=0.002,
        slippage=0.001,
        freq='15T'
    )
    
    total_return = portfolio.total_return()
    sharpe = portfolio.sharpe_ratio()
    max_dd = portfolio.max_drawdown()
    win_rate = portfolio.trades.win_rate()
    total_trades = portfolio.trades.count()
    profit_factor = portfolio.trades.profit_factor()
    calmar = portfolio.calmar_ratio()
    
    if sharpe > 1.0 and abs(max_dd) < 0.20:
        status = "PASS"
    else:
        status = "FAIL"
        
    start_date = df.index.min().strftime('%Y-%m-%d')
    end_date = df.index.max().strftime('%Y-%m-%d')
    
    report = f"""═══════════════════════════════════════
AdaptiveTrendMR Strategy Backtest — ETHUSD 15m
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
        "strategy": "AdaptiveTrendMR",
        "symbol": "ETHUSD",
        "timeframe": "15m",
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
    with open(out_dir / "adaptive_eth_15m.json", "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    main()
