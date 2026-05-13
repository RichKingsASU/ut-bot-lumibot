from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from strategies.ut_bot import UTBotStrategy

# Define the symbols to test
symbol = "SPY"

# Define the timeframe
backtesting_start = datetime(2026, 1, 1)
backtesting_end = datetime(2026, 5, 1)

# Initialize the strategy
strategy = UTBotStrategy(
    name="UT Bot Backtest",
    symbol=symbol,
    # Parameters can be passed here if needed
)

# Run the backtest
print(f"Starting backtest for {symbol}...")
strategy.backtest(
    YahooDataBacktesting,
    backtesting_start,
    backtesting_end,
    benchmark_asset="SPY",
)
print("Backtest completed successfully.")
