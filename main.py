import signal
import sys

from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from strategies.ut_bot import UTBotStrategy
from config import ALPACA_CONFIG
import adapters.supabase_logger as db


def _shutdown_handler(signum, frame):
    """Graceful shutdown — log session end to Supabase."""
    sig_name = signal.Signals(signum).name if signum else "UNKNOWN"
    print(f"\n[SHUTDOWN] Received {sig_name} — logging session end...")
    db.log_session_end()
    sys.exit(0)


def main():
    # Generate a unique session ID
    session_id = db.generate_session_id()
    print(f"Session ID: {session_id}")

    # Supabase connectivity check
    db.check_connectivity()

    # Register shutdown handlers
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    # Instantiate Alpaca broker
    broker = Alpaca(ALPACA_CONFIG)

    # Instantiate strategy
    strategy = UTBotStrategy(broker=broker)

    # Log session start
    symbol = strategy.parameters.get("symbol", "SPY")
    db.log_session_start(symbol, metadata={
        "broker": "alpaca_paper",
        "strategy": "UTBotStrategy",
        "parameters": {k: str(v) for k, v in strategy.parameters.items()},
    })

    # Instantiate trader and add strategy
    trader = Trader()
    trader.add_strategy(strategy)

    # Run the trader
    print("Starting Lumibot Trader...")
    try:
        trader.run_all()
    finally:
        # Ensure session end is logged even on unexpected exit
        db.log_session_end()


if __name__ == "__main__":
    main()
