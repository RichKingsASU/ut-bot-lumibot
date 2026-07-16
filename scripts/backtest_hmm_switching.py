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
import sys
from datetime import date, datetime
from pathlib import Path

# Repo root on sys.path so `core`/`backtests` import when run as a script
# (python3 scripts/backtest_hmm_switching.py puts scripts/, not the root, on the path).
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np
import pandas as pd
from hmmlearn import hmm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("HMMSwitchingBacktester")

# ─────────────────────────────────────────────────────────────────────────────
# Cost model — per-side transaction cost by asset class. EXPLICIT, never global.
#
# The previous global default of 0.001 (10bp/side) was a crypto-grade taker fee
# applied to equities. Measured on SPY 2000-2026: 645 round trips x 2 sides x 10bp
# = 129% of notional paid in fees, converting a -28.6% gross into a -80.4% net.
# See docs/hmm_signal_diagnosis.md.
#
# equity_etf 1bp/side  — SPY/IWM/QQQ: penny-wide lit spread, zero commission.
# crypto     10bp/side — taker-fee territory on retail venues.
# ─────────────────────────────────────────────────────────────────────────────
FEE_PER_SIDE = {
    "equity_etf": 0.0001,
    "crypto": 0.001,
}
CRYPTO_SYMBOLS = {"ETHUSD", "BTCUSD", "SOLUSD"}

# Volatility targeting (defect 4): size to a constant risk budget rather than to
# semantic regime labels. Phase 1 showed the BULL=1.0/BEAR=0.4 map was
# anti-correlated with forward returns (BULL -2.8% ann vs BEAR +7.9% ann).
TARGET_VOL_ANN = 0.15
SIZE_FLOOR, SIZE_CAP = 0.2, 1.0
MIN_DWELL_BARS = 5      # defect 5: a sizing state must persist this long to be adopted
SIZE_GRID = 0.05        # size quantum the dwell filter operates on
TRADING_DAYS = 252


def asset_class_for(symbol: str) -> str:
    return "crypto" if symbol.upper().replace("/", "") in CRYPTO_SYMBOLS else "equity_etf"


def fee_for_symbol(symbol: str) -> float:
    """Per-side transaction cost for this symbol's asset class."""
    return FEE_PER_SIDE[asset_class_for(symbol)]

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

    # Normalize the index to tz-aware UTC before comparing. Parquet files vary:
    # the Alpaca-sourced ones carry tz-aware UTC timestamps, synthetic bars are naive.
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        df.index.name = "timestamp"

    # Filter by dates — both sides UTC-aware to match the index.
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
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

def run_rolling_hmm(df_feats, lookback=252):
    """Fit HMM on rolling windows and output daily regime predictions.

    Returns ``(regimes, hmm_vol_ann)`` where ``hmm_vol_ann`` is the predicted
    state's emission mean for the ``volatility`` feature (column 1 of
    extract_features), de-standardized back to raw units and annualised — the
    HMM's own view of current risk, used by vol-target variant (a).

    No look-ahead: the window is ``vals[t-lookback:t]``, so the regime and vol
    stamped at bar t are inferred from data through bar t-1 only.
    """
    log.info(f"Running rolling HMM fitting (lookback={lookback} days)...")
    regimes = pd.Series("QUIET", index=df_feats.index)
    hmm_vol = pd.Series(np.nan, index=df_feats.index)
    vol_col = list(df_feats.columns).index("volatility")

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

            # De-standardize this state's volatility emission mean back to raw
            # daily-return-stdev units, then annualise.
            vol_daily = model.means_[current_state, vol_col] * w_std[vol_col] + w_mean[vol_col]
            hmm_vol.iloc[t] = max(float(vol_daily), 0.0) * np.sqrt(TRADING_DAYS)
        except Exception as e:
            # Fall back to previous regime if fitting fails
            regimes.iloc[t] = regimes.iloc[t-1]
            hmm_vol.iloc[t] = hmm_vol.iloc[t-1]

        if t % 200 == 0:
            log.info(f"Processed HMM rolling window step {t}/{n_samples}...")

    return regimes, hmm_vol

def vol_target_size(vol_ann: pd.Series, target_vol: float = TARGET_VOL_ANN,
                    floor: float = SIZE_FLOOR, cap: float = SIZE_CAP) -> pd.Series:
    """size_t = clip(target_vol / vol_est_t, floor, cap).

    Non-positive / missing vol estimates size to the cap (a vol estimate of zero
    implies no risk, hence no reason to shrink).
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = target_vol / vol_ann.replace(0.0, np.nan)
    return raw.clip(lower=floor, upper=cap).fillna(cap)


def apply_min_dwell(states: pd.Series, n_bars: int = MIN_DWELL_BARS) -> pd.Series:
    """Adopt a new state only after it has persisted ``n_bars`` consecutive bars.

    Defect 5: the raw regime/vol state flips on ~42% of bars, so sizing chased noise.
    Uses only past/present bars — no look-ahead: the new state is adopted on the
    n-th bar of its run, never retroactively.
    """
    if n_bars <= 1 or len(states) == 0:
        return states.copy()
    out = []
    current = states.iloc[0]
    candidate, run = current, 0
    for s in states:
        if s == current:
            candidate, run = current, 0
        else:
            if s == candidate:
                run += 1
            else:
                candidate, run = s, 1
            if run >= n_bars:
                current, run = candidate, 0
        out.append(current)
    return pd.Series(out, index=states.index)


def quantize_size(sizes: pd.Series, grid: float = SIZE_GRID) -> pd.Series:
    """Snap continuous sizes to a discrete grid so 'state change' is well defined
    for both the HMM and the rolling-stdev variant (and so dwell is comparable)."""
    return (sizes / grid).round() * grid


def churn_rate(states: pd.Series) -> float:
    """Fraction of bars on which the state changes."""
    if len(states) < 2:
        return float("nan")
    return float((states != states.shift()).iloc[1:].mean())


def realized_vol_ann(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Plain trailing realized volatility, annualised. Uses returns through bar t
    only, so it is known at t and applied to the t -> t+1 return."""
    return df["close"].pct_change().rolling(window).std() * np.sqrt(TRADING_DAYS)


def count_round_trips(positions: pd.Series) -> int:
    """Number of entries (flat -> long transitions)."""
    prev = positions.shift(1).fillna(0.0)
    return int(((positions > 0) & (prev == 0)).sum())


def simulate_portfolio(df, positions, sizes, init_cash=100000.0, *, fee_pct) -> pd.Series:
    """Simulate equity curve given a position series, trade sizing, and fees.

    ``fee_pct`` (per side) is keyword-only and REQUIRED — there is deliberately no
    default. A global default is what let a 10bp crypto fee run against equities
    unnoticed. Resolve it via ``fee_for_symbol(symbol)``, or pass 0.0 for gross.

    NOTE on sizing semantics: ``sizes`` is read only on bars where the position
    signal changes, i.e. size is fixed at entry for the life of the trade; it does
    not rebalance intra-trade. This is pre-existing execution behaviour, left
    untouched by design.
    """
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

def evaluate_variant(name, df, positions, sizes, init_cash, fee_pct) -> dict:
    """Run one variant twice — gross (fee=0) and net — so the cost of turnover is
    always visible side by side. The gross/net gap is the overtrading diagnostic.
    """
    eq_gross = simulate_portfolio(df, positions, sizes, init_cash, fee_pct=0.0)
    eq_net = simulate_portfolio(df, positions, sizes, init_cash, fee_pct=fee_pct)
    m_gross = evaluate_metrics(eq_gross, init_cash)
    m_net = evaluate_metrics(eq_net, init_cash)

    # fee drag: the fraction of terminal gross equity consumed by fees
    fee_drag = 1.0 - (eq_net.iloc[-1] / eq_gross.iloc[-1]) if eq_gross.iloc[-1] > 0 else float("nan")

    return {
        "name": name,
        "gross_return": m_gross["total_return"],
        "net_return": m_net["total_return"],
        "gross_sharpe": m_gross["sharpe_ratio"],
        "sharpe_ratio": m_net["sharpe_ratio"],
        "max_drawdown": m_net["max_drawdown"],
        "gross_max_drawdown": m_gross["max_drawdown"],
        "round_trips": count_round_trips(positions),
        "fee_drag_pct": float(fee_drag),
        "fee_pct_per_side": fee_pct,
        "avg_size": float(sizes.mean()),
    }

def main():
    p = argparse.ArgumentParser(description="HMM State-Conditioned Strategy Backtester")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--start", type=_date, default=date(2020, 1, 1))
    p.add_argument("--end", type=_date, default=date(2026, 7, 1))
    p.add_argument("--init-cash", type=float, default=100000.0, dest="init_cash")
    p.add_argument("--min-dwell", type=int, default=MIN_DWELL_BARS, dest="min_dwell",
                   help="bars a sizing state must persist before it is adopted (defect 5)")
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
    
    fee = fee_for_symbol(args.symbol)
    log.info(f"Cost model: asset_class={asset_class_for(args.symbol)} "
             f"fee_pct={fee} per side ({fee * 1e4:.0f}bp)")

    # 2. Extract features and run HMM rolling fitting
    df_feats = extract_features(df)
    regimes, hmm_vol = run_rolling_hmm(df_feats, lookback=252)

    # Align original dataframe to matching features index
    df_align = df.loc[regimes.index]

    # 3. Compute the signal. calculate_ut_signals is UNCHANGED and shared by every
    #    variant, so all signal variants trade identically — only size differs.
    log.info("Calculating strategy signals...")
    pos_baseline = calculate_ut_signals(df_align, atr_period=10, sensitivity=1.0)
    pos_hold = pd.Series(1.0, index=df_align.index)
    full_size = pd.Series(1.0, index=df_align.index)

    # 4. Sizing — volatility targeting (defect 4), two independent vol estimates.
    #    (a) the HMM's own emission vol   (b) a plain 20-day trailing stdev
    size_a_raw = vol_target_size(hmm_vol.reindex(df_align.index))
    size_b_raw = vol_target_size(realized_vol_ann(df_align, window=20))

    # 5. Min-dwell (defect 5) on the quantized size state, applied identically to
    #    both variants so the (a) vs (b) comparison stays like-for-like.
    size_a_q, size_b_q = quantize_size(size_a_raw), quantize_size(size_b_raw)
    size_a = apply_min_dwell(size_a_q, args.min_dwell)
    size_b = apply_min_dwell(size_b_q, args.min_dwell)

    # Headline question: does the HMM's vol estimate differ from a 20-day stdev at all?
    _hv = hmm_vol.reindex(df_align.index)
    _rv = realized_vol_ann(df_align, window=20)
    _both = pd.concat([_hv, _rv], axis=1).dropna()
    agreement = {
        "corr_hmm_vol_vs_rvol20": float(_both.iloc[:, 0].corr(_both.iloc[:, 1])),
        "corr_size_a_vs_size_b": float(size_a.corr(size_b)),
        "pct_bars_identical_size": float((size_a == size_b).mean()),
        "mean_hmm_vol_ann": float(_hv.mean()),
        "mean_rvol20_ann": float(_rv.mean()),
    }

    churn = {
        "regime_label": churn_rate(regimes),
        "hmm_size_before_dwell": churn_rate(size_a_q),
        "hmm_size_after_dwell": churn_rate(size_a),
        "rvol_size_before_dwell": churn_rate(size_b_q),
        "rvol_size_after_dwell": churn_rate(size_b),
    }

    # 6. Run every variant gross AND net
    log.info("Simulating: buy & hold benchmark...")
    v_hold = evaluate_variant("Buy & Hold (benchmark)", df_align, pos_hold, full_size,
                              args.init_cash, fee)
    log.info("Simulating: baseline signal, fixed 100% size...")
    v_base = evaluate_variant("Baseline signal (100% size)", df_align, pos_baseline,
                              full_size, args.init_cash, fee)
    log.info("Simulating: vol-target (a) HMM emission vol...")
    v_a = evaluate_variant("Vol-target (a) HMM emission vol", df_align, pos_baseline,
                           size_a, args.init_cash, fee)
    log.info("Simulating: vol-target (b) 20d realized vol...")
    v_b = evaluate_variant("Vol-target (b) 20d realized vol", df_align, pos_baseline,
                           size_b, args.init_cash, fee)

    variants = [v_hold, v_base, v_a, v_b]

    hdr = (f"{'Variant':<34}{'Gross':>9}{'Net':>9}{'Sharpe':>8}"
           f"{'MaxDD':>9}{'Trades':>8}{'FeeDrag':>9}{'AvgSize':>9}")
    rows = "\n".join(
        f"{v['name']:<34}{v['gross_return']:>8.1%}{v['net_return']:>9.1%}"
        f"{v['sharpe_ratio']:>8.2f}{v['max_drawdown']:>9.1%}"
        f"{v['round_trips']:>8d}{v['fee_drag_pct']:>9.1%}{v['avg_size']:>9.2f}"
        for v in variants
    )
    report = f"""\
{prov_str}
COST MODEL: asset_class={asset_class_for(args.symbol)} | fee={fee} per side ({fee * 1e4:.0f}bp) | \
gross = same run at fee=0
════════════════════════════════════════════════════════════════════════════════════════
Vol-Targeted Sizing Backtest — {args.symbol}  (target_vol={TARGET_VOL_ANN:.0%} ann, \
size clip [{SIZE_FLOOR}, {SIZE_CAP}], min_dwell={args.min_dwell} bars)
════════════════════════════════════════════════════════════════════════════════════════
{hdr}
{'─' * 88}
{rows}
════════════════════════════════════════════════════════════════════════════════════════
Sizing-state churn (fraction of bars the state changes):
  HMM regime label (no dwell, for reference) : {churn['regime_label']:.1%}
  (a) HMM vol size    before dwell : {churn['hmm_size_before_dwell']:.1%}  \
after : {churn['hmm_size_after_dwell']:.1%}
  (b) 20d rvol size   before dwell : {churn['rvol_size_before_dwell']:.1%}  \
after : {churn['rvol_size_after_dwell']:.1%}

Do (a) and (b) measure the same thing? — is the HMM earning its complexity?
  corr(HMM emission vol, 20d realized vol) : {agreement['corr_hmm_vol_vs_rvol20']:+.3f}
  corr(size_a, size_b)                     : {agreement['corr_size_a_vs_size_b']:+.3f}
  bars with identical size                 : {agreement['pct_bars_identical_size']:.1%}
  mean vol est: HMM {agreement['mean_hmm_vol_ann']:.1%} ann vs 20d rvol \
{agreement['mean_rvol20_ann']:.1%} ann

NOTE: size is fixed at entry and does not rebalance intra-trade (pre-existing engine
behaviour, unchanged). Signal is identical across variants, so trade counts match —
only size differs. Defect 2 (no signal edge) is untouched by design.
════════════════════════════════════════════════════════════════════════════════════════"""
    print(report)
    
    # Save comparison data — gross AND net always reported side by side.
    results = {
        "symbol": args.symbol,
        "start": args.start.isoformat(),
        "end": args.end.isoformat(),
        "data_provenance": sd.provenance.value,
        "data_rows": sd.rows,
        "cost_model": {
            "asset_class": asset_class_for(args.symbol),
            "fee_pct_per_side": fee,
            "fee_bp_per_side": fee * 1e4,
        },
        "sizing": {
            "method": "volatility_target",
            "target_vol_ann": TARGET_VOL_ANN,
            "size_floor": SIZE_FLOOR,
            "size_cap": SIZE_CAP,
            "size_grid": SIZE_GRID,
            "min_dwell_bars": args.min_dwell,
        },
        "churn": churn,
        "vol_estimate_agreement": agreement,
        "metrics": {v["name"]: v for v in variants},
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
