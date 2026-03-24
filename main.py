from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from strategies.ut_bot import UTBotStrategy
from config import ALPACA_CONFIG

def main():
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
