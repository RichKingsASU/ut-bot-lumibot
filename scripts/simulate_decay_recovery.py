#!/usr/bin/env python3
"""
Simulated Edge Decay & Recovery Runner.
Simulates a stream of trades transitioning from a healthy edge to decay and
subsequent recovery. Tests how quickly the SignalDecayMonitor detects these
transitions and scales allocations to protect portfolio equity.

Usage:
  python3 scripts/simulate_decay_recovery.py
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("DecayRecoverySim")

# System Thresholds from SignalDecayMonitor
IC_HEALTHY_THRESHOLD = 0.02
IC_DEGRADING_THRESHOLD = 0.005
IC_DEAD_THRESHOLD = 0.0
LOOKBACK = 30

def generate_trade_stream(n_healthy=50, n_decay=50, n_recovery=50) -> list:
    """Generate simulated trades with transition phases."""
    np.random.seed(101)  # Seed for deterministic tests
    trades = []
    
    # Helper to generate a single trade
    def make_trade(win_rate, avg_win, avg_loss, std_win, std_loss):
        # Random signal direction: Buy (1) or Sell (-1)
        sig = np.random.choice([1, -1])
        is_win = np.random.random() < win_rate
        if is_win:
            abs_pnl = np.random.normal(avg_win, std_win)
            abs_pnl = max(abs_pnl, 0.0001)
            pnl = abs_pnl  # Winning trade
        else:
            abs_pnl = np.random.normal(avg_loss, std_loss)
            abs_pnl = min(abs_pnl, -0.0001)
            pnl = abs_pnl  # Losing trade
            
        # PnL matches signal direction: return = sig * pnl
        # (Winning shorts align positively)
        return {
            "sig": int(sig),
            "pnl": float(pnl),
            # matched return format expected by Spearman calc
            "matched_return": float(sig * pnl)
        }

    # Phase 1: Healthy Edge (win rate = 56%, average win = 2.0%, average loss = -1.2%)
    for _ in range(n_healthy):
        trades.append(make_trade(0.56, 0.02, -0.012, 0.005, 0.004))
        
    # Phase 2: Decayed Edge (win rate = 32%, average win = 1.0%, average loss = -1.8%)
    for _ in range(n_decay):
        trades.append(make_trade(0.32, 0.01, -0.018, 0.004, 0.005))
        
    # Phase 3: Recovered Edge (win rate = 56%, average win = 2.0%, average loss = -1.2%)
    for _ in range(n_recovery):
        trades.append(make_trade(0.56, 0.02, -0.012, 0.005, 0.004))
        
    return trades

def calculate_ic_scalar(ic: float) -> float:
    """Map IC score to Kelly sizer multiplier."""
    if ic is None:
        return 1.0
    if ic >= IC_HEALTHY_THRESHOLD:
        return 1.0
    elif ic >= IC_DEGRADING_THRESHOLD:
        return 0.75
    elif ic >= IC_DEAD_THRESHOLD:
        return 0.50
    else:
        return 0.0

def run_simulation(trades, lookback=LOOKBACK):
    """Run rolling IC analysis and evaluate capital sizing responses."""
    log.info(f"Running rolling IC analysis over {len(trades)} trades...")
    
    ic_scores = []
    ic_scalars = []
    
    # Pad first lookback window with 1.0 sizers
    for i in range(lookback):
        ic_scores.append(0.05)  # Mock healthy start
        ic_scalars.append(1.0)
        
    for t in range(lookback, len(trades)):
        window = trades[t-lookback:t]
        
        signal_scores = [w["sig"] for w in window]
        actual_returns = [w["sig"] * w["pnl"] for w in window]
        
        try:
            ic, _ = spearmanr(signal_scores, actual_returns)
            if np.isnan(ic):
                ic = 0.0
        except Exception:
            ic = 0.0
            
        ic_scores.append(float(ic))
        ic_scalars.append(calculate_ic_scalar(ic))
        
    # Measure Latencies
    decay_start = min(50, len(trades))
    recovery_start = min(100, len(trades))
    
    warning_index = None
    shutdown_index = None
    recovery_index = None
    
    # 1. Decay detection (after index 50)
    if decay_start < len(trades):
        for i in range(decay_start, min(recovery_start, len(trades))):
            if warning_index is None and ic_scalars[i] < 1.0:
                warning_index = i
            if shutdown_index is None and ic_scalars[i] == 0.0:
                shutdown_index = i
            
    # 2. Recovery detection (after index 100)
    if recovery_start < len(trades):
        for i in range(recovery_start, len(trades)):
            if ic_scalars[i] == 1.0:
                recovery_index = i
                break
            
    warning_latency = (warning_index - decay_start) if warning_index else None
    shutdown_latency = (shutdown_index - decay_start) if shutdown_index else None
    recovery_latency = (recovery_index - recovery_start) if recovery_index else None
    
    log.info(f"Warning Latency: {warning_latency} trades")
    log.info(f"Shutdown Latency: {shutdown_latency} trades")
    log.info(f"Recovery Latency: {recovery_latency} trades")
    
    # 3. Simulate Equity Curves (Static vs Adaptive)
    cash_static = 100000.0
    cash_adaptive = 100000.0
    
    eq_static = [cash_static]
    eq_adaptive = [cash_adaptive]
    
    for i in range(len(trades)):
        pnl_pct = trades[i]["pnl"]
        
        # Static allocations: always trade 10% capital
        alloc_static = cash_static * 0.10
        cash_static += alloc_static * pnl_pct
        eq_static.append(cash_static)
        
        # Adaptive allocations: scale the 10% alloc by previous trade's ic_scalar
        scalar = ic_scalars[i-1] if i > 0 else 1.0
        alloc_adaptive = cash_adaptive * 0.10 * scalar
        cash_adaptive += alloc_adaptive * pnl_pct
        eq_adaptive.append(cash_adaptive)
        
    return {
        "ic_scores": ic_scores,
        "ic_scalars": ic_scalars,
        "warning_latency_trades": warning_latency,
        "shutdown_latency_trades": shutdown_latency,
        "recovery_latency_trades": recovery_latency,
        "eq_static": eq_static,
        "eq_adaptive": eq_adaptive,
        "final_static": cash_static,
        "final_adaptive": cash_adaptive,
        "capital_saved": cash_adaptive - cash_static
    }

def main():
    import argparse
    from core.data_provenance import DataProvenance, enforce_provenance, SyntheticDataError
    
    p = argparse.ArgumentParser(description="Edge Decay & Recovery Simulator")
    p.add_argument("--allow-synthetic", action="store_true", help="allow running on synthetic data explicitly")
    args = p.parse_args()

    allow_synthetic = args.allow_synthetic or os.getenv("ALLOW_SYNTHETIC", "").lower() in ("true", "1") or os.getenv("TRADING_MODE", "").lower() == "research"
    
    prov = DataProvenance.SYNTHETIC_DECAY
    enforce_provenance(prov, allow_synthetic=allow_synthetic)

    prov_str = f"⚠️ DATA PROVENANCE: {prov.value.upper()} — RESULTS DO NOT REFLECT REAL MARKET DATA"
    log.info(prov_str)

    log.info("Starting Simulated Edge Decay & Recovery Simulation...")
    trades = generate_trade_stream()
    log.info(f"Generated trade stream with {len(trades)} trades.")
    
    res = run_simulation(trades)
    
    # Calculate returns and drawdowns
    eq_stat = pd.Series(res["eq_static"])
    eq_adapt = pd.Series(res["eq_adaptive"])
    
    static_ret = (res["final_static"] - 100000.0) / 100000.0
    adapt_ret = (res["final_adaptive"] - 100000.0) / 100000.0
    
    max_dd_static = ((eq_stat - eq_stat.cummax()) / eq_stat.cummax()).min()
    max_dd_adapt = ((eq_adapt - eq_adapt.cummax()) / eq_adapt.cummax()).min()
    
    report = f"""\
{prov_str}
════════════════════════════════════════════════════════════
Edge Decay & Recovery Simulation Report
════════════════════════════════════════════════════════════
LATENCY METRICS:
  Decay Warning Latency  : {res['warning_latency_trades']} trades
  Decay Shutdown Latency : {res['shutdown_latency_trades']} trades
  Edge Recovery Latency  : {res['recovery_latency_trades']} trades

PORTFOLIO PERFORMANCE COMPARISON:
  Static Allocation (Fixed 10% Sizing):
    Total Return : {static_ret:.1%}
    Max Drawdown : {max_dd_static:.1%}
    Final Equity : ${res['final_static']:,.2f}

  Adaptive Allocation (Dynamic IC Scaling):
    Total Return : {adapt_ret:.1%}
    Max Drawdown : {max_dd_adapt:.1%}
    Final Equity : ${res['final_adaptive']:,.2f}

  CAPITAL PRESERVED (SAVED) : ${res['capital_saved']:,.2f}
════════════════════════════════════════════════════════════"""
    print(report)
    
    # Prepare results JSON
    results = {
        "data_provenance": prov.value,
        "warning_latency_trades": res["warning_latency_trades"],
        "shutdown_latency_trades": res["shutdown_latency_trades"],
        "recovery_latency_trades": res["recovery_latency_trades"],
        "static_metrics": {
            "total_return": float(static_ret),
            "max_drawdown": float(max_dd_static),
            "final_equity": float(res["final_static"])
        },
        "adaptive_metrics": {
            "total_return": float(adapt_ret),
            "max_drawdown": float(max_dd_adapt),
            "final_equity": float(res["final_adaptive"])
        },
        "capital_saved": float(res["capital_saved"]),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Save results
    out_dir = Path("/mnt/tick-storage/backtest_results")
    written = False
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "decay_recovery_simulation.json"
        with open(out_file, "w") as f:
            json.dump(results, f, indent=4)
        log.info(f"Saved decay simulation results to: {out_file}")
        written = True
    except Exception:
        pass
        
    if not written:
        out_dir = Path("backtests/results")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "decay_recovery_simulation.json"
        with open(out_file, "w") as f:
            json.dump(results, f, indent=4)
        log.info(f"Saved decay simulation results to: {out_file} (fallback)")
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
