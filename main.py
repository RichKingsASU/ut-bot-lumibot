import signal
import sys

from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from strategies.ut_bot import UTBotStrategy
from strategies import heartbeat
from config import ALPACA_CONFIG


def _shutdown_handler(signum, frame):
    """Handle SIGINT/SIGTERM — write offline status before exit."""
    print(f"\nReceived signal {signum}, shutting down...")
    heartbeat.stop()
    sys.exit(0)


def main():
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    # Start heartbeat (writes to Supabase every 30s)
    heartbeat.start()

    # Instantiate Alpaca broker
    broker = Alpaca(ALPACA_CONFIG)

    # Instantiate strategy
    strategy = UTBotStrategy(broker=broker)

    # Instantiate trader and add strategy
    trader = Trader()
    trader.add_strategy(strategy)

    # Run the trader
    print("Starting Lumibot Trader...")
    trader.run_all()

if __name__ == "__main__":
    main()
