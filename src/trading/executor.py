import os
import sys
import time
import logging
from datetime import datetime
import pytz

try:
    import fcntl
except ImportError:
    fcntl = None

from broker import (
    get_open_position, get_daily_realized_pnl, get_daily_trade_count,
    buy_to_open, sell_to_close, cancel_all_orders
)
from signal_engine import evaluate_signal
from risk_supervisor import RiskSupervisor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("executor")
ET = pytz.timezone("America/New_York")

LOCK_FILE = "/tmp/ut_bot.lock"

# Simple local state to supplement authoritative broker state
_local_state = {
    "entry_underlying_price": None,
    "entry_rsi": None,
    "last_signal_time": None
}

def acquire_lock():
    if fcntl is None:
        logger.warning("fcntl not available, skipping lock (Windows?)")
        return None
    try:
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("Acquired single-instance lock.")
        return lock_fd
    except (IOError, BlockingIOError):
        logger.error("CRITICAL: Another instance of the bot is already running. Exiting.")
        sys.exit(1)

def main_loop():
    lock_fd = acquire_lock()
    
    # Configuration
    config = {
        "SYMBOL": "SPY",
        "MAX_DAILY_LOSS": os.getenv("MAX_DAILY_LOSS", "500.0"),
        "MAX_TRADES_PER_DAY": os.getenv("MAX_TRADES_PER_DAY", "10"),
        "MAX_POSITION_SIZE": int(os.getenv("MAX_POSITION_SIZE", "1")),
        "EOD_FLATTEN_TIME": os.getenv("EOD_FLATTEN_TIME", "15:55"),
        "RSI_STEP_THRESH": os.getenv("RSI_STEP_THRESH", "5.0"),
        "STOP_PCT": os.getenv("STOP_PCT", "0.005")
    }
    
    supervisor = RiskSupervisor(broker=None, config=config)
    symbol = config["SYMBOL"]
    
    logger.info("Starting Execution Engine Loop...")
    
    while True:
        try:
            # 1. RISK SUPERVISOR CADENCE (Every 5 seconds)
            time.sleep(5)
            
            # Authoritative State Sync
            position = get_open_position(symbol)
            daily_pnl = get_daily_realized_pnl()
            daily_trades = get_daily_trade_count()
            
            # Reconstruct local entry state if we have a position
            if position:
                position["entry_underlying_price"] = _local_state["entry_underlying_price"]
                position["entry_rsi"] = _local_state["entry_rsi"]
            else:
                _local_state["entry_underlying_price"] = None
                _local_state["entry_rsi"] = None
                
            # Local Kill Switch
            if supervisor.is_kill_switch_active():
                logger.error("LOCAL KILL SWITCH ACTIVE! Cancelling orders and flattening.")
                cancel_all_orders(symbol)
                if position:
                    sell_to_close(position["contract_symbol"], position["qty"])
                continue # Block all further processing
                
            # EOD Flatten
            if supervisor.check_eod_flatten():
                if position:
                    logger.info("EOD Flatten triggered.")
                    cancel_all_orders(symbol)
                    sell_to_close(position["contract_symbol"], position["qty"])
                continue # Block entries past EOD flatten time
                
            # Evaluate Data & Signals
            sig_data = evaluate_signal(symbol)
            current_price = sig_data["price"]
            current_rsi = sig_data["rsi_5m"]
            signal = sig_data["signal"]
            
            # Position Management (Exit Logic)
            if position:
                exit_reason = supervisor.check_exit_triggers(position, current_price, current_rsi)
                if exit_reason:
                    logger.info(f"Exit triggered: {exit_reason}")
                    sell_to_close(position["contract_symbol"], position["qty"])
                elif signal != 0:
                    # Strategy flip or close signal (e.g. signal=-1 while LONG)
                    if (position["direction"] == "LONG" and signal == -1) or \
                       (position["direction"] == "SHORT" and signal == 1):
                        logger.info("Signal flipped. Exiting position.")
                        sell_to_close(position["contract_symbol"], position["qty"])
                continue # Do not attempt to enter a new position while holding one
                
            # Entry Logic (If no position)
            # Evaluate daily signal exactly at 15:45 ET to avoid intraday noise,
            # or if testing, we might evaluate it constantly.
            # But the prompt said "15:45+ entry gating". We'll enforce this.
            now_et = datetime.now(ET)
            if now_et.hour != 15 or now_et.minute < 45:
                # Outside entry window, just wait.
                continue
                
            if signal == 0:
                continue # No signal
                
            # Check Limits
            if not supervisor.enforce_limits(daily_pnl, daily_trades):
                continue
                
            # EXECUTE ENTRY
            direction = "LONG" if signal == 1 else "SHORT"
            logger.info(f"SIGNAL DETECTED: {direction} {symbol}. Executing BTO...")
            
            res = buy_to_open(symbol, direction, config["MAX_POSITION_SIZE"])
            if res and res.get("status") == "filled":
                _local_state["entry_underlying_price"] = current_price
                _local_state["entry_rsi"] = current_rsi
                logger.info(f"Entry filled successfully.")
            else:
                logger.warning(f"Entry failed or was rejected.")
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(5) # Prevent tight crash loop
            
if __name__ == "__main__":
    main_loop()
