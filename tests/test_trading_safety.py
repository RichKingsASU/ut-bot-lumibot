import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytz

import sys
import os
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from trading.risk_supervisor import RiskSupervisor

ET = pytz.timezone("America/New_York")

@pytest.fixture
def risk_supervisor():
    config = {
        "MAX_DAILY_LOSS": "500.0",
        "MAX_TRADES_PER_DAY": "10",
        "STOP_PCT": "0.005",
        "RSI_STEP_THRESH": "5.0"
    }
    return RiskSupervisor(broker=None, config=config)

def test_enforce_limits(risk_supervisor):
    assert risk_supervisor.enforce_limits(daily_pnl=100.0, daily_trades=5) == True
    assert risk_supervisor.enforce_limits(daily_pnl=-550.0, daily_trades=5) == False
    assert risk_supervisor.enforce_limits(daily_pnl=-500.0, daily_trades=5) == False
    assert risk_supervisor.enforce_limits(daily_pnl=100.0, daily_trades=10) == False

def test_exit_trigger_rsi_stepback(risk_supervisor):
    position = {"entry_rsi": 70.0, "direction": "LONG"}
    assert risk_supervisor.check_exit_triggers(position, current_price=100.0, current_rsi=65.0) is not None
    assert risk_supervisor.check_exit_triggers(position, current_price=100.0, current_rsi=66.0) is None

def test_exit_trigger_trailing_stop_long(risk_supervisor):
    position = {"entry_underlying_price": 100.0, "direction": "LONG"}
    assert risk_supervisor.check_exit_triggers(position, current_price=99.5, current_rsi=50.0) is not None
    assert risk_supervisor.check_exit_triggers(position, current_price=99.6, current_rsi=50.0) is None

def test_exit_trigger_defensive_types(risk_supervisor):
    position = {"entry_underlying_price": None, "entry_rsi": None, "direction": "LONG"}
    assert risk_supervisor.check_exit_triggers(position, current_price=100.0, current_rsi=50.0) is None
    
    position = {"entry_underlying_price": 100.0, "entry_rsi": 50.0, "direction": "LONG"}
    assert risk_supervisor.check_exit_triggers(position, current_price=None, current_rsi=None) is None
    assert risk_supervisor.check_exit_triggers(position, current_price=0.0, current_rsi=50.0) is None
    assert risk_supervisor.check_exit_triggers(position, current_price=math.nan, current_rsi=50.0) is None

@patch('os.path.exists')
def test_kill_switch(mock_exists, risk_supervisor):
    mock_exists.return_value = True
    assert risk_supervisor.is_kill_switch_active() == True
