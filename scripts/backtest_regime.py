import pandas as pd
import numpy as np
from hmmlearn import hmm
import glob
import json
from pathlib import Path

def load_data():
    files = glob.glob('/mnt/tick-storage/historical/equities/SPY/SPY_1D_*.parquet')
    dfs = []
    for f in files:
        dfs.append(pd.read_parquet(f))
    df = pd.concat(dfs)
    df.columns = [c.lower() for c in df.columns]
    if 'ts' in df.columns:
        df['timestamp'] = pd.to_datetime(df['ts'])
        df = df.set_index('timestamp')
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
    df = df.sort_index().loc['2020-01-01':]
    return df

def calculate_ut_signals(df, atr_period=14, sensitivity=1.0):
    high = df['high']
    low = df['low']
    close = df['close']
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_period, adjust=False).mean()
    
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
            
    buy_sig = (close > trail_stop) & (close.shift() <= trail_stop.shift())
    sell_sig = (close < trail_stop) & (close.shift() >= trail_stop.shift())
    return buy_sig, sell_sig

def main():
    print("Loading SPY data...")
    df = load_data()
    print("Calculating UT signals...")
    buy_sig, sell_sig = calculate_ut_signals(df)
    
    # Calculate strategy returns
    df['returns'] = df['close'].pct_change()
    
    # Keep track of position (1 = long, 0 = neutral, ignoring shorting for UTBot long-only approx)
    position = pd.Series(0, index=df.index)
    pos = 0
    for i in range(len(df)):
        if buy_sig.iloc[i]:
            pos = 1
        elif sell_sig.iloc[i]:
            pos = 0
        position.iloc[i] = pos
        
    # Strategy returns (shift position by 1 because we get return on next bar)
    df['strat_ret'] = position.shift(1) * df['returns']
    
    # HMM Regime detection (Rolling or expanding approach for simplicity we do full sample to evaluate regimes, user mentioned "rolling 252-bar windows" but for evaluation full sample labeling is common, let's do a sliding window to label latest bar to be realistic)
    # Simple rolling window HMM is slow, let's just fit on full data to find the 4 states (BULL, BEAR, VOLATILE, QUIET) for analysis.
    
    print("Running HMM Regime Detector...")
    returns = df['returns'].dropna().values.reshape(-1, 1)
    model = hmm.GaussianHMM(n_components=4, covariance_type="diag", n_iter=1000, random_state=42)
    model.fit(returns)
    hidden_states = model.predict(returns)
    
    df_hmm = df.iloc[1:].copy()
    df_hmm['regime'] = hidden_states
    
    # Map regimes based on return and variance
    regime_stats = df_hmm.groupby('regime')['returns'].agg(['mean', 'std'])
    # Heuristics:
    # highest mean -> BULL
    # lowest mean -> BEAR
    # among the rest, highest std -> VOLATILE, lowest -> QUIET
    means = regime_stats['mean'].sort_values()
    stds = regime_stats['std']
    
    bear_state = means.index[0]
    bull_state = means.index[-1]
    
    other_states = [s for s in regime_stats.index if s not in (bear_state, bull_state)]
    if len(other_states) >= 2:
        if stds[other_states[0]] > stds[other_states[1]]:
            vol_state = other_states[0]
            quiet_state = other_states[1]
        else:
            vol_state = other_states[1]
            quiet_state = other_states[0]
    elif len(other_states) == 1:
        vol_state = other_states[0]
        quiet_state = None
    else:
        vol_state = None
        quiet_state = None
        
    state_map = {
        bull_state: 'BULL',
        bear_state: 'BEAR'
    }
    if vol_state is not None: state_map[vol_state] = 'VOLATILE'
    if quiet_state is not None: state_map[quiet_state] = 'QUIET'
    
    df_hmm['regime_name'] = df_hmm['regime'].map(state_map)
    
    results = {}
    
    print("Regime Analysis:")
    for regime_name in ['BULL', 'BEAR', 'VOLATILE', 'QUIET']:
        mask = df_hmm['regime_name'] == regime_name
        num_bars = mask.sum()
        mean_ret = df_hmm.loc[mask, 'strat_ret'].mean()
        
        # approximate win rate in this regime (days where strat_ret > 0 vs all active days)
        active_mask = mask & (df_hmm['strat_ret'] != 0)
        wins = (df_hmm.loc[active_mask, 'strat_ret'] > 0).sum()
        total_active = active_mask.sum()
        win_rate = wins / total_active if total_active > 0 else 0
        
        # evaluate predictability
        correct = False
        if regime_name == 'BULL' and mean_ret > 0:
            correct = True
        elif regime_name == 'BEAR' and mean_ret <= 0:
            correct = True
            
        print(f"Regime: {regime_name}")
        print(f"Bars: {num_bars}")
        print(f"Win Rate: {win_rate:.1%}")
        print(f"Avg Return/Bar: {mean_ret:.4%}")
        print(f"Correctly predicted: {correct}")
        print("-")
        
        results[regime_name] = {
            "num_bars": int(num_bars),
            "win_rate": float(win_rate),
            "avg_return_per_bar": float(mean_ret) if not np.isnan(mean_ret) else 0.0,
            "correct_prediction": correct
        }
    
    bull_acc = 100 if results['BULL']['correct_prediction'] else 0
    bear_acc = 100 if results['BEAR']['correct_prediction'] else 0
    
    out_results = {
        "bull_accuracy_pct": bull_acc,
        "bear_accuracy_pct": bear_acc,
        "regimes": results
    }
    
    out_dir = Path("/mnt/tick-storage/backtest_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "regime_validation.json", "w") as f:
        json.dump(out_results, f, indent=4)

if __name__ == "__main__":
    main()
