import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import Mock

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import agents.signal_decay_monitor as sdm
from agents.signal_decay_monitor import SignalDecayMonitor

def test_ic_direction():
    # Force MIN_TRADES to 1 so we can calculate IC on thin samples
    orig_min_trades = sdm.MIN_TRADES
    sdm.MIN_TRADES = 1
    try:
        # IC calculation is pure business logic; injected collaborators keep this
        # unit test independent of Qdrant, model packages, and model downloads.
        vector_client = Mock()
        embed_model = Mock()
        monitor = SignalDecayMonitor(
            'test-monitor', qdrant_client=vector_client, embed_model=embed_model
        )
        assert monitor.qdrant_client is vector_client
        assert monitor._injected_embed_model is embed_model
        
        # 4 synthetic matched pairs with a positive edge (predictive signal):
        # 1. winning long:  sig = +1, pnl = +0.05
        # 2. winning short: sig = -1, pnl = +0.05
        # 3. losing long:   sig = +1, pnl = -0.02
        # 4. losing short:  sig = -1, pnl = -0.02
        signals = []
        outcomes = []
        base_time = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
        
        test_cases = [
            (True, False, 0.05),   # winning long
            (False, True, 0.05),   # winning short
            (True, False, -0.02),  # losing long
            (False, True, -0.02),  # losing short
        ]
        
        for i, (buy, sell, pnl) in enumerate(test_cases):
            time_str = (base_time + timedelta(hours=i)).isoformat()
            signals.append({
                "created_at": time_str,
                "buy_sig": buy,
                "sell_sig": sell,
                "signal_type": "ut_bot"
            })
            outcomes.append({
                "created_at": time_str,
                "pnl_pct": pnl,
                "signal_type": "ut_bot"
            })
            
        ic = monitor.calculate_ic(signals, outcomes)
        
        print(f"Calculated IC for predictive set: {ic}")
        assert ic is not None
        assert ic > 0.0, f"Expected positive IC for predictive signal, got {ic}"
        
    finally:
        sdm.MIN_TRADES = orig_min_trades
