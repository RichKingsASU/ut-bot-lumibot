import os
from datetime import datetime
from supabase import create_client
import pandas as pd
from lumibot.backtesting import PandasDataBacktesting
from lumibot.entities import Asset, Data
from dotenv import load_dotenv

# Add strategies to path if needed
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from strategies.ut_bot import UTBotStrategy

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def fetch_bars_from_supabase(symbol, timeframe, start, end):
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    response = client.table("ohlcv_bars") \
      .select("ts,open,high,low,close,volume") \
      .eq("symbol", symbol) \
      .eq("timeframe", timeframe) \
      .gte("ts", start.isoformat()) \
      .lte("ts", end.isoformat()) \
      .order("ts") \
      .execute()
      
    if not response.data:
        print(f"No data found for {symbol} {timeframe} from {start} to {end}")
        return pd.DataFrame()

    df = pd.DataFrame(response.data)
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df.index = df.index.tz_convert("America/New_York")
    df.columns = ["open","high","low","close","volume"]
    # Ensure columns are numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col])
    return df

def run_supabase_backtest(symbol, timeframe, start, end):
    print(f"Running backtest for {symbol} using Supabase data...")
    df = fetch_bars_from_supabase(symbol, timeframe, start, end)
    
    if df.empty:
        return None

    asset = Asset(symbol=symbol, asset_type="stock")
    data = Data(
      asset=asset,
      df=df,
      timestep=timeframe,
      date_start=start,
      date_end=end
    )
    pandas_data = {asset: data}
    
    strategy = UTBotStrategy(
      broker=None,
      backtesting_datasource=PandasDataBacktesting,
      parameters={
        "symbol": symbol,
        "atr_period": 10,
        "sensitivity": 1.0,
        "timeframe": timeframe
      }
    )
    
    result = strategy.run_backtest(
      PandasDataBacktesting,
      start,
      end,
      pandas_data=pandas_data,
      parameters={"symbol": symbol}
    )
    return result

if __name__ == "__main__":
    # Example usage
    symbol = "IWM"
    timeframe = "15m"
    start = datetime(2024, 1, 1)
    end = datetime(2024, 12, 31)
    
    result = run_supabase_backtest(
      symbol=symbol,
      timeframe=timeframe,
      start=start,
      end=end
    )
    if result:
        print(f"Backtest Completed. Portfolio Value: {result.portfolio_value}")
    else:
        print("Backtest failed due to missing data.")
