import os
import logging
from datetime import datetime
import pytz
import math

logger = logging.getLogger("risk_supervisor")
ET = pytz.timezone("America/New_York")

# Constants
KILL_SWITCH_PATH = "/run/disrupting-alpha/trading-disabled"
ABSOLUTE_DAILY_LOSS_LIMIT = 5000.0
MAX_QUOTE_AGE_SECONDS = 30

def _is_valid_float(val):
    if val is None:
        return False
    try:
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval) or fval <= 0:
            return False
        return True
    except (ValueError, TypeError):
        return False

class RiskSupervisor:
    def __init__(self, broker, config):
        self.broker = broker
        self.config = config
        
    def is_kill_switch_active(self) -> bool:
        """Check if local kill switch file exists."""
        if os.path.exists(KILL_SWITCH_PATH):
            return True
        return False
        
    def enforce_limits(self, daily_pnl: float, daily_trades: int) -> bool:
        """Return True if trading is allowed, False if blocked by limits."""
        max_loss = min(float(self.config.get("MAX_DAILY_LOSS", 500.0)), ABSOLUTE_DAILY_LOSS_LIMIT)
        if daily_pnl <= -max_loss:
            logger.error(f"CRITICAL: DAILY LOSS LIMIT REACHED (${daily_pnl:.2f}) - Trading suspended.")
            return False
            
        max_trades = int(self.config.get("MAX_TRADES_PER_DAY", 10))
        if daily_trades >= max_trades:
            logger.warning(f"MAX_TRADES_PER_DAY ({max_trades}) reached. Entry blocked.")
            return False
            
        return True
        
    def check_exit_triggers(self, position: dict, current_price: float, current_rsi: float) -> str | None:
        """Check if an open position should be exited based on risk rules."""
        
        # 1. Check RSI step-back
        entry_rsi = position.get("entry_rsi")
        
        if _is_valid_float(entry_rsi) and _is_valid_float(current_rsi):
            rsi_drop = entry_rsi - current_rsi
            if rsi_drop >= float(self.config.get("RSI_STEP_THRESH", 5.0)):
                return f"rsi_stepback (entry={entry_rsi:.1f} now={current_rsi:.1f})"
                
        # 2. Trailing stop on underlying price
        entry_price = position.get("entry_underlying_price")
        
        # If we don't have entry price, we can't calculate trailing stop
        # If current_price is invalid, we can't compare
        if _is_valid_float(entry_price) and _is_valid_float(current_price):
            stop_pct = float(self.config.get("STOP_PCT", 0.005))
            
            if position.get("direction") == "LONG":
                if current_price <= entry_price * (1 - stop_pct):
                    return f"trailing_stop_long (entry={entry_price:.2f} now={current_price:.2f})"
            elif position.get("direction") == "SHORT":
                if current_price >= entry_price * (1 + stop_pct):
                    return f"trailing_stop_short (entry={entry_price:.2f} now={current_price:.2f})"
                
        return None
