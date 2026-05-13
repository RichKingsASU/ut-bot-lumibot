from adapters.json_logger import setup_logging
setup_logging()

import signal
import sys
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from strategies.ut_bot import UTBotStrategy
from strategies import heartbeat
from config import ALPACA_CONFIG
import adapters.supabase_logger as db


def _shutdown_handler(signum, frame):
    print(f"\nReceived signal {signum}, shutting down...")
    from strategies.health_server import set_ready
    set_ready(False)  # Signal not ready
    heartbeat.stop()
    # Allow 1s for cleanup
    import time
    time.sleep(1)
    sys.exit(0)


from strategies.options_executor import sync_state_with_broker

from logger import bot_logger, ErrorCategory

def main():
    session_id = db.generate_session_id()
    bot_logger.info(f"Bot Session Started: {session_id}", category=ErrorCategory.INFRASTRUCTURE)
    
    if not db.check_connectivity():
        bot_logger.error("Supabase Connectivity Failed. Operational integrity at risk.", category=ErrorCategory.INFRASTRUCTURE)
    
    from config_validator import validate_production_env
    try:
        validate_production_env()
    except Exception as e:
        bot_logger.error(f"Environment Validation Failed: {e}", category=ErrorCategory.SECURITY)
        sys.exit(1)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    from strategies.health_server import start_health_server, set_ready
    start_health_server(8000)

    # ── [RELIABILITY FIX] Sync state with broker before starting ─────────
    try:
        sync_state_with_broker("SPY") 
    except Exception as e:
        bot_logger.warning(f"Initial Broker Sync Failed: {e}. Retrying during strategy loop.")
    
    set_ready(True)

    try:
        broker = Alpaca(ALPACA_CONFIG)
        strategy = UTBotStrategy(broker=broker)
        symbol = strategy.parameters.get("symbol", "SPY")
        
        db.log_session_start(symbol, metadata={
            "broker": "alpaca_paper" if ALPACA_CONFIG.get("PAPER") else "alpaca_live",
            "strategy": "UTBotStrategy",
            "parameters": {k: str(v) for k, v in strategy.parameters.items()},
        })
        
        trader = Trader()
        trader.add_strategy(strategy)
        heartbeat.start()
        
        bot_logger.info("Starting Lumibot Trader Loop...", category=ErrorCategory.INFRASTRUCTURE)
        trader.run_all()
        
    except Exception as e:
        bot_logger.error(f"Fatal crash in trade loop: {e}", category=ErrorCategory.CRITICAL, exc_info=True)
    finally:
        bot_logger.info("Initiating Graceful Shutdown...", category=ErrorCategory.INFRASTRUCTURE)
        heartbeat.stop()
        db.log_session_end()


if __name__ == "__main__":
    main()
