import sys
import subprocess
import json
from pathlib import Path

def main():
    print("Running backtest_utbot.py...")
    subprocess.run([sys.executable, "scripts/backtest_utbot.py"], check=True)
    
    print("Running backtest_adaptive.py...")
    subprocess.run([sys.executable, "scripts/backtest_adaptive.py"], check=True)
    
    print("Running backtest_regime.py...")
    subprocess.run([sys.executable, "scripts/backtest_regime.py"], check=True)
    
    results_dir = Path("/mnt/tick-storage/backtest_results")
    
    with open(results_dir / "utbot_spy_daily.json") as f:
        ut_data = json.load(f)
        
    with open(results_dir / "adaptive_eth_15m.json") as f:
        ad_data = json.load(f)
        
    with open(results_dir / "regime_validation.json") as f:
        reg_data = json.load(f)
        
    ut_sharpe = ut_data.get('sharpe_ratio', 0)
    ut_dd = ut_data.get('max_drawdown', 0)
    ut_win = ut_data.get('win_rate', 0)
    ut_status = ut_data.get('status', 'FAIL')
    
    ad_sharpe = ad_data.get('sharpe_ratio', 0)
    ad_dd = ad_data.get('max_drawdown', 0)
    ad_win = ad_data.get('win_rate', 0)
    ad_status = ad_data.get('status', 'FAIL')
    
    bull_acc = reg_data.get('bull_accuracy_pct', 0)
    bear_acc = reg_data.get('bear_accuracy_pct', 0)
    
    if ut_status == "PASS" and ad_status == "PASS":
        overall = "READY"
    else:
        overall = "NOT READY"
        
    report = f"""═══════════════════════════════════════
DISRUPTING ALPHA — BACKTEST SUMMARY
═══════════════════════════════════════
UTBot SPY Daily:
  Sharpe: {ut_sharpe:.2f} | Drawdown: {ut_dd:.1%} | Win: {ut_win:.1%}
  Status: {ut_status}

AdaptiveTrendMR ETH 15m:
  Sharpe: {ad_sharpe:.2f} | Drawdown: {ad_dd:.1%} | Win: {ad_win:.1%}
  Status: {ad_status}

Regime Accuracy:
  BULL correctly predicted: {bull_acc}%
  BEAR correctly predicted: {bear_acc}%

OVERALL: {overall} for live trading"""

    print(report)
    
    summary = {
        "UTBot_SPY_Daily": ut_data,
        "AdaptiveTrendMR_ETH_15m": ad_data,
        "Regime_Accuracy": reg_data,
        "Overall": overall
    }
    
    with open(results_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=4)

if __name__ == "__main__":
    main()
