import os
import logging
from datetime import datetime
import pytz

logger = logging.getLogger("risk_supervisor")
ET = pytz.timezone("America/New_York")

# Constants
KILL_SWITCH_PATH = "/tmp/trading-disabled"
ABSOLUTE_DAILY_LOSS_LIMIT = 5000.0
MAX_QUOTE_AGE_SECONDS = 30

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
        
    def check_eod_flatten(self) -> bool:
        """Return True if EOD flatten should be triggered."""
        now_et = datetime.now(ET)
        
        # NOTE: A real implementation would use pandas_market_calendars to check 
        # if today is a trading day and what the close time is.
        # For this minimal implementation, we enforce a strict 15:55 ET flatten.
        eod_time = self.config.get("EOD_FLATTEN_TIME", "15:55")
        fh, fm = map(int, eod_time.split(":"))
        
        # Flatten triggers at or after the eod time, but resets at midnight
        if now_et.hour > fh or (now_et.hour == fh and now_et.minute >= fm):
            return True
        return False
        
    def check_exit_triggers(self, position: dict, current_price: float, current_rsi: float) -> str | None:
        """Check if an open position should be exited based on risk rules."""
        # 1. Check RSI step-back
        # Since we use broker state now, we might not have entry_rsi on restart.
        # But we pass it if we have it locally. (Handled in Executor)
        entry_rsi = position.get("entry_rsi")
        if entry_rsi is not None:
            rsi_drop = entry_rsi - current_rsi
            if rsi_drop >= float(self.config.get("RSI_STEP_THRESH", 5.0)):
                return f"rsi_stepback (entry={entry_rsi:.1f} now={current_rsi:.1f})"
                
        # 2. Trailing stop on underlying price
        # Also requires entry underlying price, which we might lack on restart.
        entry_price = position.get("entry_underlying_price", current_price)
        stop_pct = float(self.config.get("STOP_PCT", 0.005))
        
        if position.get("direction") == "LONG":
            if current_price <= entry_price * (1 - stop_pct):
                return f"trailing_stop_long (entry={entry_price:.2f} now={current_price:.2f})"
        elif position.get("direction") == "SHORT":
            if current_price >= entry_price * (1 + stop_pct):
                return f"trailing_stop_short (entry={entry_price:.2f} now={current_price:.2f})"
                
        return None
