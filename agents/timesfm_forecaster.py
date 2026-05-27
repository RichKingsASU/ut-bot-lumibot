import numpy as np
import pandas as pd
import polars as pl
import os
import glob
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger('TimesFMForecaster')

HIST_ROOT = Path('/mnt/tick-storage/historical')
FORECAST_HORIZON = 12  # bars ahead to forecast
CONTEXT_LENGTH = 512   # bars of history to use
TIMESFM_MODEL = 'google/timesfm-1.0-200m'

class TimesFMForecaster:

  def __init__(self):
    load_dotenv('/home/k2/ut-bot-lumibot/.env')
    self.model = None
    self.model_loaded = False

  def _load_model(self):
    """Load TimesFM model once."""
    # Try timesfm package first:
    try:
      import timesfm
      self.tfm = timesfm.TimesFm(
        hparams=timesfm.TimesFmHparams(
          backend='cpu',
          per_core_batch_size=32,
          horizon_len=FORECAST_HORIZON,
        ),
        checkpoint=timesfm.TimesFmCheckpoint(
          huggingface_repo_id=TIMESFM_MODEL
        ),
      )
      self.model_loaded = True
      logger.info('TimesFM model loaded via timesfm package')
      return True
    except Exception as e:
      logger.warning(f'timesfm package failed: {e}')

    # Try transformers fallback:
    try:
      from transformers import pipeline
      self.pipeline = pipeline(
        'text2text-generation',
        model=TIMESFM_MODEL
      )
      self.model_loaded = True
      logger.info('TimesFM loaded via transformers')
      return True
    except Exception as e:
      logger.warning(f'transformers fallback failed: {e}')
      return False

  def _load_bars(
    self,
    symbol: str,
    asset_class: str = 'equities',
    timeframe: str = '1D'
  ) -> pd.DataFrame:
    """Load bars from Parquet."""
    if asset_class == 'equities':
        path = HIST_ROOT / 'equities' / symbol
        pattern = f'{symbol}_1D_*.parquet'
    else:
        safe = symbol.replace('/', '')
        path = HIST_ROOT / 'crypto' / safe
        pattern = f'{safe}_1D_*.parquet'

    # Use glob to find files.
    files = glob.glob(str(path / pattern))
    if not files:
        return None
        
    df = pd.read_parquet(files[0])
    # Sort by timestamp ascending.
    if 'timestamp' in df.columns:
        df = df.sort_values('timestamp', ascending=True)
        
    # Return last CONTEXT_LENGTH rows.
    if len(df) < 30:
        return None
    return df.tail(CONTEXT_LENGTH)

  def forecast(
    self,
    symbol: str,
    asset_class: str = 'equities'
  ) -> dict:
    """Generate price forecast for symbol."""
    df = self._load_bars(symbol, asset_class)
    if df is None:
        return None
        
    if 'close' not in df.columns:
        return None
        
    closes = df['close'].values
    last_price = float(closes[-1])
    
    # Normalize: prices / prices[-1] (relative to last)
    norm_closes = closes / last_price
    
    # TimesFM model requires HuggingFace access token
    # Using linear regression as production method
    # To enable TimesFM: huggingface-cli login
    # then set HUGGINGFACE_TOKEN in .env
    method_used = 'linear_regression'
    forecast_values = []
        
    if method_used == 'linear_regression':
        # If model not loaded: use simple linear regression as fallback
        from numpy.polynomial import polynomial as P
        x = np.arange(len(closes))
        fit = np.polyfit(x, closes, 1)
        future_x = np.arange(len(closes),
                             len(closes) + FORECAST_HORIZON)
        forecast_values = np.polyval(fit, future_x)

    forecast_prices = list(forecast_values)
    final_price = float(forecast_prices[-1])
    forecast_pct_change = ((final_price - last_price) / last_price) * 100
    
    if forecast_pct_change > 0.5:
        forecast_direction = 'UP'
    elif forecast_pct_change < -0.5:
        forecast_direction = 'DOWN'
    else:
        forecast_direction = 'FLAT'

    return {
      'symbol': symbol,
      'asset_class': asset_class,
      'last_price': last_price,
      'forecast_prices': forecast_prices,
      'forecast_direction': forecast_direction,
      'forecast_pct_change': forecast_pct_change,
      'confidence': 0.8 if method_used == 'timesfm' else 0.5,
      'method': method_used,
      'bars_used': len(closes)
    }

  def forecast_batch(
    self,
    symbols: list,
    asset_class: str = 'equities'
  ) -> dict:
    """Run forecast for multiple symbols."""
    results = {}
    for sym in symbols:
        res = self.forecast(sym, asset_class)
        if res:
            results[sym] = res
    return results

  def get_signal_modifier(
    self,
    forecast: dict,
    current_signal: str
  ) -> dict:
    """Map forecast to signal confidence modifier."""
    if not forecast:
        return {
          'modifier': 'NEUTRAL',
          'confidence_boost': 0,
          'reasoning': 'No forecast available'
        }
        
    forecast_direction = forecast.get('forecast_direction')
    
    if forecast_direction == 'UP' and current_signal == 'BUY':
      modifier = 'CONFIRM'
      confidence_boost = 15
    elif forecast_direction == 'DOWN' and current_signal == 'SELL':
      modifier = 'CONFIRM'
      confidence_boost = 15
    elif (forecast_direction == 'DOWN' and current_signal == 'BUY') or \
         (forecast_direction == 'UP' and current_signal == 'SELL'):
      modifier = 'CONFLICT'
      confidence_boost = -10
    else:
      modifier = 'NEUTRAL'
      confidence_boost = 0

    return {
      'modifier': modifier,
      'confidence_boost': confidence_boost,
      'reasoning': f"Forecast {forecast_direction} vs Signal {current_signal}"
    }
