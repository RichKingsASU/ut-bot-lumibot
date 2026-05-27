import logging
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.timesfm_forecaster import TimesFMForecaster

def test_timesfm():
    logging.basicConfig(level=logging.INFO)
    print("Testing TimesFM Integration...")
    
    forecaster = TimesFMForecaster()
    # Force model load
    forecaster._load_model()
    
    symbols = [('SPY', 'equities'), ('QQQ', 'equities'), ('ETH/USD', 'crypto')]
    
    for sym, asset_class in symbols:
        res = forecaster.forecast(sym, asset_class)
        if res:
            direction = res['forecast_direction']
            pct = res['forecast_pct_change']
            method = res['method']
            bars = res['bars_used']
            horizon = len(res['forecast_prices'])
            print(f"{sym} forecast: {direction} {pct:+.1f}% ({horizon} bars ahead)")
        else:
            print(f"{sym} forecast: FAILED (no data or error)")
            
    if res:
        print(f"Method: {res['method']}")
        if res['method'] in ['timesfm', 'linear_regression']:
            print("✅ TimesFM integration working")
        else:
            print("❌ TimesFM integration failed")

if __name__ == '__main__':
    test_timesfm()
