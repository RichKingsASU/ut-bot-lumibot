#!/usr/bin/env python3
"""
HMM State-Conditioned Strategy Backtester.
Fits Gaussian HMMs on a rolling 252-day lookback window to dynamically predict
market regimes (BULL, BEAR, VOLATILE, QUIET) and adjusts capital allocation (sizing)
and trailing-stop sensitivity in real time.

Usage:
  python3 scripts/backtest_hmm_switching.py --symbol SPY --start 2020-01-01
"""

import argparse
import json
import logging
import os
import glob
from datetime import date, datetime
from pathlib import Path
import numpy as np
import pandas as pd
from hmmlearn import hmm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("HMMSwitchingBacktester")

def _date(s: str) -> date:
    return date.fromisoformat(s)

def generate_synthetic_data(start_date: date, end_date: date) -> pd.DataFrame:
    """Generate high-quality synthetic daily data simulating regime transitions."""
    log.info("Generating high-quality synthetic market data for testing...")
    idx = pd.date_range(start=start_date, end=end_date, freq="D")
    n = len(idx)
    
    # Simulate a hidden state sequence (regimes)
    # State 0: BULL (high return, low vol)
    # State 1: BEAR (negative return, high vol)
    # State 2: VOLATILE (neutral return, very high vol)
    # State 3: QUIET (low return, low vol)
    states = np.zeros(n, dtype=int)
    current_state = 0
    # Transition matrix
    trans_mat = [
        [0.98, 0.01, 0.005, 0.005],
        [0.02, 0.95, 0.02, 0.01],
        [0.01, 0.03, 0.94, 0.02],
        [0.02, 0.01, 0.02, 0.95]
    ]
    np.random.seed(42)
    for i in range(1, n):
        current_state = np.random.choice(4, p=trans_mat[current_state])
        states[i] = current_state
        
    # Generate returns based on states
    means = [0.0008, -0.0012, 0.0001, 0.0002]
    vols = [0.008, 0.018, 0.025, 0.005]
    
    rets = np.zeros(n)
    for i in range(n):
        s = states[i]
        rets[i] = np.random.normal(means[s], vols[s])
        
    prices = 100.0 * np.exp(np.cumsum(rets))
    
    # Reconstruct OHLCV
    df = pd.DataFrame(index=idx)
    df["close"] = prices
    df["open"] = df["close"].shift(1).fillna(100.0) * (1.0 + np.random.normal(0, 0.001, n))
    df["high"] = df[["open", "close"]].max(axis=1) * (1.0 + np.abs(np.random.normal(0, 0.003, n)))
    df["low"] = df[["open", "close"]].min(axis=1) * (1.0 - np.abs(np.random.normal(0, 0.003, n)))
    
    # Volume: higher in volatile/bear markets
    base_vol = [1000000, 1500000, 2500000, 600000]
    df["volume"] = [float(np.random.poisson(base_vol[s])) for s in states]
    
    return df

from core.data_provenance import DataProvenance, SourcedData, enforce_provenance, SyntheticDataError

def load_data(symbol: str, start: date, end: date, *, allow_synthetic: bool = False) -> SourcedData:
    """Load daily data from local files or generate synthetic data."""
    # Check equities and crypto paths
    paths = [
        f"/mnt/tick-storage/historical/equities/{symbol}/{symbol}_1D_*.parquet",
        f"/mnt/tick-storage/historical/crypto/{symbol.replace('/', '')}/{symbol.replace('/', '')}_1D_*.parquet"
    ]
    files = []
    for p in paths:
        files.extend(glob.glob(p))
        
    df = None
    provenance = None

    if files:
        log.info(f"Loading data from parquet files: {files}")
        dfs = []
        for f in files:
            try:
                dfs.append(pd.read_parquet(f))
            except Exception as e:
                log.error(f"Error reading {f}: {e}")
                
        if dfs:
            df = pd.concat(dfs)
            provenance = DataProvenance.REAL_PARQUET
            
    if df is None:
        if not allow_synthetic:
            raise SyntheticDataError(
                f"Refusing to run: no real daily data found for {symbol} "
                f"and synthetic data is disabled. Pass --allow-synthetic to enable."
            )
        df = generate_synthetic_data(start, end)
        provenance = DataProvenance.SYNTHETIC_REGIME
        
    df.columns = [c.lower() for c in df.columns]
    
    # Normalize timestamp index
    time_col = None
    for col in ["ts", "timestamp", "date"]:
        if col in df.columns:
            time_col = col
            break
            
    if time_col:
        df["timestamp"] = pd.to_datetime(df[time_col])
        df = df.set_index("timestamp")
    elif df.index.name != "timestamp" and not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
            df.index.name = "timestamp"
        except Exception:
            pass
            
    df = df.sort_index()
    # Filter by dates
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1)
    df = df[(df.index >= start_ts) & (df.index < end_ts)]
    
    sd = SourcedData(
        data=df,
        provenance=provenance,
        rows=len(df),
        symbol=symbol
    )
    
    enforce_provenance(sd.provenance, allow_synthetic=allow_synthetic)
    return sd

def calculate_ut_signals(df, atr_period=10, sensitivity=1.0):
    """Replicate UT Bot ATR signal calculations."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(window=atr_period, min_periods=1).mean()
    
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
    
    # Forward-fill positions
    pos = pd.Series(0.0, index=df.index)
    curr_pos = 0.0
    for i in range(len(df)):
        if buy_sig.iloc[i]:
            curr_pos = 1.0
        elif sell_sig.iloc[i]:
            curr_pos = 0.0
        pos.iloc[i] = curr_pos
        
    return pos

def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract standard HMM features matching RegimeDetector."""
    feats = pd.DataFrame(index=df.index)
    feats["returns"] = df["close"].pct_change()
    feats["volatility"] = feats["returns"].rolling(window=10).std()
    
    if "volume" in df.columns:
        feats["volume_ratio"] = df["volume"] / df["volume"].rolling(window=20).mean()
    else:
        feats["volume_ratio"] = 1.0
        
    feats["range_ratio"] = (df["high"] - df["low"]) / df["close"]
    return feats.dropna()

def map_regimes(model, X_window) -> dict:
    """Map HMM hidden states to semantic names: BULL, BEAR, VOLATILE, QUIET."""
    means = model.means_
    returns_col = means[:, 0]
    vol_col = means[:, 1]
    
    state_regimes = {}
    sorted_by_returns = np.argsort(returns_col)
    
    state_regimes[sorted_by_returns[-1]] = "BULL"
    state_regimes[sorted_by_returns[0]] = "BEAR"
    
    remaining = [s for s in range(len(means)) if s not in state_regimes]
    vol_remaining = sorted(remaining, key=lambda x: vol_col[x], reverse=True)
    
    state_regimes[vol_remaining[0]] = "VOLATILE"
    state_regimes[vol_remaining[1]] = "QUIET"
    
    return state_regimes

def run_rolling_hmm(df_feats, lookback=252) -> pd.Series:
    """Fit HMM on rolling windows and output daily regime predictions."""
    log.info(f"Running rolling HMM fitting (lookback={lookback} days)...")
    regimes = pd.Series("QUIET", index=df_feats.index)
    
    # Standardize values in a rolling manner
    vals = df_feats.values
    n_samples = len(vals)
    
    for t in range(lookback, n_samples):
        # Rolling window slice
        window = vals[t-lookback:t]
        
        # Standardize features within this window
        w_mean = np.mean(window, axis=0)
        w_std = np.std(window, axis=0)
        w_std[w_std == 0] = 1.0
        window_std = (window - w_mean) / w_std
        
        # Fit Gaussian HMM
        model = hmm.GaussianHMM(
            n_components=4,
            covariance_type="diag",
            n_iter=100,
            random_state=42
        )
        try:
            model.fit(window_std)
            # Predict the hidden state of the latest bar
            states = model.predict(window_std)
            current_state = states[-1]
            
            # Map states to names
            state_map = map_regimes(model, window_std)
            regimes.iloc[t] = state_map.get(current_state, "QUIET")
        except Exception as e:
            # Fall back to previous regime if fitting fails
            regimes.iloc[t] = regimes.iloc[t-1]
            
        if t % 200 == 0:
            log.info(f"Processed HMM rolling window step {t}/{n_samples}...")
            
    return regimes

def simulate_portfolio(df, positions, sizes, init_cash=100000.0, fee_pct=0.001) -> pd.Series:
    """Simulate equity curve given a position series, trade sizing, and fees."""
    cash = init_cash
    pos_shares = 0.0
    equity_curve = []
    
    # Align variables
    close = df["close"].values
    pos_signals = positions.values
    trade_sizes = sizes.values
    
    # Track yesterday's position to subtract trade fees
    prev_pos = 0.0
    
    for i in range(len(df)):
        price = close[i]
        sig = pos_signals[i]
        sz = trade_sizes[i]
        
        # Calculate current portfolio value (equity)
        current_equity = cash + (pos_shares * price)
        equity_curve.append(current_equity)
        
        # Check if position changes (trading event)
        if sig != prev_pos:
            # Exit previous position
            if pos_shares > 0.0:
                cash += pos_shares * price * (1.0 - fee_pct)
                pos_shares = 0.0
                
            # Enter new position with current trade size multiplier
            if sig > 0.0:
                target_value = current_equity * sz
                shares_to_buy = target_value / price
                cash_required = target_value * (1.0 + fee_pct)
                
                # Verify cash limits
                if cash_required > cash:
                    shares_to_buy = (cash / price) * (1.0 - fee_pct)
                    cash = 0.0
                else:
                    cash -= cash_required
                    
                pos_shares = shares_to_buy
                
            prev_pos = sig
            
    # Final flatten
    if pos_shares > 0.0:
        cash += pos_shares * close[-1] * (1.0 - fee_pct)
        pos_shares = 0.0
        
    equity_curve[-1] = cash
    return pd.Series(equity_curve, index=df.index)

def evaluate_metrics(eq_curve, init_cash) -> dict:
    """Calculate key performance indicators."""
    total_ret = (eq_curve.iloc[-1] - init_cash) / init_cash
    
    # Sharpe ratio
    daily_returns = eq_curve.pct_change().dropna()
    std = daily_returns.std()
    mean = daily_returns.mean()
    sharpe = (mean / std) * np.sqrt(252) if std > 0 else 0.0
    
    # Drawdown
    cum_max = eq_curve.cummax()
    drawdowns = (eq_curve - cum_max) / cum_max
    max_dd = drawdowns.min()
    
    return {
        "total_return": float(total_ret),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd)
    }

def main():
    p = argparse.ArgumentParser(description="HMM State-Conditioned Strategy Backtester")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--start", type=_date, default=date(2020, 1, 1))
    p.add_argument("--end", type=_date, default=date(2026, 7, 1))
    p.add_argument("--init-cash", type=float, default=100000.0, dest="init_cash")
    p.add_argument("--allow-synthetic", action="store_true", help="allow running on synthetic data explicitly")
    args = p.parse_args()
    
    allow_synthetic = args.allow_synthetic or os.getenv("ALLOW_SYNTHETIC", "").lower() in ("true", "1") or os.getenv("TRADING_MODE", "").lower() == "research"
    
    # 1. Load data
    sd = load_data(args.symbol, args.start, args.end, allow_synthetic=allow_synthetic)
    df = sd.data
    log.info(f"Loaded {len(df)} daily bars of data.")
    
    if sd.provenance.is_synthetic:
        prov_str = f"⚠️ DATA PROVENANCE: {sd.provenance.value.upper()} — RESULTS DO NOT REFLECT REAL MARKET DATA"
    else:
        prov_str = f"DATA PROVENANCE: {sd.provenance.value} | rows={sd.rows} | symbol={args.symbol}"
    log.info(prov_str)
    
    # 2. Extract features and run HMM rolling fitting
    df_feats = extract_features(df)
    regimes = run_rolling_hmm(df_feats, lookback=252)
    
    # Align original dataframe to matching features index
    df_align = df.loc[regimes.index]
    
    # 3. Compute baseline and adapted signals
    log.info("Calculating strategy signals...")
    pos_baseline = calculate_ut_signals(df_align, atr_period=10, sensitivity=1.0)
    pos_adapted_tighter = calculate_ut_signals(df_align, atr_period=10, sensitivity=0.7)
    
    # 4. Define sizing arrays
    sizing_regime = regimes.map({
        "BULL": 1.0,
        "QUIET": 0.8,
        "VOLATILE": 0.6,
        "BEAR": 0.4
    }).fillna(0.8)
    
    # Dynamic signal switching: use tighter exits during volatile or bear regimes
    pos_regime_adapted = pd.Series(index=df_align.index, dtype=float)
    for i in range(len(df_align)):
        reg = regimes.iloc[i]
        if reg in ["BEAR", "VOLATILE"]:
            pos_regime_adapted.iloc[i] = pos_adapted_tighter.iloc[i]
        else:
            pos_regime_adapted.iloc[i] = pos_baseline.iloc[i]
            
    # 5. Run simulations
    log.info("Simulating portfolio variation 1: Baseline...")
    eq_baseline = simulate_portfolio(df_align, pos_baseline, pd.Series(1.0, index=df_align.index), args.init_cash)
    
    log.info("Simulating portfolio variation 2: Regime-Sized...")
    eq_sized = simulate_portfolio(df_align, pos_baseline, sizing_regime, args.init_cash)
    
    log.info("Simulating portfolio variation 3: Regime-Adapted...")
    eq_adapted = simulate_portfolio(df_align, pos_regime_adapted, sizing_regime, args.init_cash)
    
    # 6. Evaluate metrics
    metrics_baseline = evaluate_metrics(eq_baseline, args.init_cash)
    metrics_sized = evaluate_metrics(eq_sized, args.init_cash)
    metrics_adapted = evaluate_metrics(eq_adapted, args.init_cash)
    
    report = f"""\
{prov_str}
════════════════════════════════════════════════════════════
HMM State-Conditioned Sizing Backtest — {args.symbol}
════════════════════════════════════════════════════════════
Baseline (Fixed 100% Size, Fixed sensitivity 1.0):
  Total Return : {metrics_baseline['total_return']:.1%}
  Sharpe Ratio : {metrics_baseline['sharpe_ratio']:.2f}
  Max Drawdown : {metrics_baseline['max_drawdown']:.1%}

Regime-Sized (Regime-Adjusted Sizing, Fixed sensitivity 1.0):
  Total Return : {metrics_sized['total_return']:.1%}
  Sharpe Ratio : {metrics_sized['sharpe_ratio']:.2f}
  Max Drawdown : {metrics_sized['max_drawdown']:.1%}

Regime-Adapted (Regime-Adjusted Sizing + Tighter sensitivity 0.7 in BEAR/VOL):
  Total Return : {metrics_adapted['total_return']:.1%}
  Sharpe Ratio : {metrics_adapted['sharpe_ratio']:.2f}
  Max Drawdown : {metrics_adapted['max_drawdown']:.1%}
════════════════════════════════════════════════════════════"""
    print(report)
    
    # Save comparison data
    results = {
        "symbol": args.symbol,
        "start": args.start.isoformat(),
        "end": args.end.isoformat(),
        "data_provenance": sd.provenance.value,
        "data_rows": sd.rows,
        "metrics": {
            "baseline": metrics_baseline,
            "regime_sized": metrics_sized,
            "regime_adapted": metrics_adapted
        }
    }
    
    out_dir = Path("/mnt/tick-storage/backtest_results")
    written = False
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "hmm_switching_comparison.json"
        with open(out_file, "w") as f:
            json.dump(results, f, indent=4)
        log.info(f"Saved HMM backtest comparison report to: {out_file}")
        written = True
    except Exception:
        pass
        
    if not written:
        out_dir = Path("backtests/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "hmm_switching_comparison.json"
        with open(out_file, "w") as f:
            json.dump(results, f, indent=4)
        log.info(f"Saved HMM backtest comparison report to: {out_file} (fallback)")
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
