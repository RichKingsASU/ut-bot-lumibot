import pandas as pd
import numpy as np
from lumibot.strategies.strategy import Strategy

class UTBotStrategy(Strategy):
    parameters = {
        "symbol": "SPY",
        "atr_period": 1,
        "sensitivity": 1.0,
        "timeframe": "1D",
    }

    def initialize(self):
        self.sleeptime = "1D"
        self.last_signal = None

    def on_trading_iteration(self):
        symbol = self.parameters["symbol"]
        atr_period = self.parameters["atr_period"]
        sensitivity = self.parameters["sensitivity"]

        # Fetch historical prices
        bars = self.get_historical_prices(symbol, 100, "day")
        df = bars.df

        # Calculate ATR manually
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift())
        df['low_close'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=atr_period).mean()

        # Calculate UT Bot Trailing Stop
        df['loss'] = sensitivity * df['atr']
        df['trail_stop'] = 0.0
        
        # We need to iterate over the dataframe to calculate the trailing stop correctly based on previous values
        for i in range(1, len(df)):
            close = df.iloc[i]['close']
            prev_close = df.iloc[i-1]['close']
            prev_trail_stop = df.iloc[i-1]['trail_stop']
            loss = df.iloc[i]['loss']

            if close > prev_trail_stop and prev_close > prev_trail_stop:
                df.at[df.index[i], 'trail_stop'] = max(prev_trail_stop, close - loss)
            elif close < prev_trail_stop and prev_close < prev_trail_stop:
                df.at[df.index[i], 'trail_stop'] = min(prev_trail_stop, close + loss)
            elif close > prev_trail_stop:
                df.at[df.index[i], 'trail_stop'] = close - loss
            else:
                df.at[df.index[i], 'trail_stop'] = close + loss

        # Signal logic
        df['prev_trail_stop'] = df['trail_stop'].shift()
        df['signal'] = 0
        df.loc[(df['close'] > df['trail_stop']) & (df['close'].shift() <= df['prev_trail_stop']), 'signal'] = 1
        df.loc[(df['close'] < df['trail_stop']) & (df['close'].shift() >= df['prev_trail_stop']), 'signal'] = -1

        current_price = df.iloc[-1]['close']
        current_trail_stop = df.iloc[-1]['trail_stop']
        current_signal = df.iloc[-1]['signal']
        
        # Get current position
        position = self.get_position(symbol)
        
        self.log_message(f"Price: {current_price}, Trail Stop: {current_trail_stop}, Signal: {current_signal}, Position: {position}")

        if current_signal == 1 and position is None:
            # Buy signal and no position
            quantity = self.get_quantity(current_price)
            order = self.create_order(symbol, quantity, "buy")
            self.submit_order(order)
            self.log_message(f"BUY order submitted for {quantity} shares of {symbol}")
        
        elif current_signal == -1 and position is not None:
            # Sell signal and position exists
            self.sell_all()
            self.log_message(f"SELL ALL order submitted for {symbol}")

    def get_quantity(self, price):
        cash = self.get_cash()
        # Use full portfolio allocation
        quantity = int(cash / price)
        return quantity
