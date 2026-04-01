import signal
import sys
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from strategies.ut_bot import UTBotStrategy
from strategies import heartbeat
from config import ALPACA_CONFIG
import adapters.supabase_logger as db


def _shutdown_handler(signum, frame):
    """Handle SIGINT/SIGTERM - write offline status before exit."""
    print(f"\nReceived signal {signum}, shutting down...")
    heartbeat.stop()
    sys.exit(0)


def main():
    session_id = db.generate_session_id()
    print(f"Session ID: {session_id}")
    db.check_connectivity()
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)
    broker = Alpaca(ALPACA_CONFIG)
    strategy = UTBotStrategy(broker=broker)
    symbol = strategy.parameters.get("symbol", "SPY")
    db.log_session_start(symbol, metadata={
        "broker": "alpaca_paper",
        "strategy": "UTBotStrategy",
        "parameters": {k: str(v) for k, v in strategy.parameters.items()},
    })
    trader = Trader()
    trader.add_strategy(strategy)
    print("Starting Lumibot Trader...")
    try:
        trader.run_all()
    finally:
        db.log_session_end()


if __name__ == "__main__":
    main()
