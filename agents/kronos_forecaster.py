"""
Kronos Financial Foundation Model forecaster.
AAAI 2026 — trained on 12B K-line records from 45 global exchanges.
93% better RankIC than leading TSFMs in zero-shot forecasting.

Architecture notes (from reading /home/k2/Kronos/model/kronos.py):
  - KronosTokenizer: BSQ-based OHLCV tokenizer (encodes to bit-indices)
  - Kronos: decoder-only transformer over quantized tokens
  - KronosPredictor.predict(): takes DataFrame[open,high,low,close,volume]
      + x_timestamp (Series) + y_timestamp (Series of future dates)
      → returns pred_df[open,high,low,close,volume,amount] indexed by y_timestamp

Runs via subprocess bridge into /home/k2/kronos-venv to isolate PyTorch
from the main trading venv. Interface mirrors TimesFMForecaster for easy
parallel comparison and eventual swap/ensemble.

Model selection:
  - kronos-mini  : 4.1M params, 2048-token context (fastest, default for CPU)
  - kronos-small : 24.7M params, 512-token context (more accurate)
"""
import os
import sys
import json
import logging
import subprocess
import tempfile
import datetime
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger('KronosForecaster')

# ─── Paths ────────────────────────────────────────────────────────────────────
KRONOS_VENV_PYTHON = '/home/k2/kronos-venv/bin/python3'
KRONOS_REPO        = '/home/k2/Kronos'
KRONOS_MODELS_DIR  = '/home/k2/kronos-models'

MODEL_CONFIG = {
    'mini': {
        'model_path':     f'{KRONOS_MODELS_DIR}/kronos-mini',
        'tokenizer_path': f'{KRONOS_MODELS_DIR}/tokenizer-2k',
        'max_context':    2048,
        'params':         '4.1M',
    },
    'small': {
        'model_path':     f'{KRONOS_MODELS_DIR}/kronos-small',
        'tokenizer_path': f'{KRONOS_MODELS_DIR}/tokenizer-base',
        'max_context':    512,
        'params':         '24.7M',
    },
}

DEFAULT_MODEL = 'mini'

# ─── Alpaca credentials (mirrors timesfm_forecaster pattern) ─────────────────
_ALPACA_KEY    = os.getenv('ALPACA_API_KEY') or os.getenv('APCA_API_KEY_ID')
_ALPACA_SECRET = os.getenv('ALPACA_API_SECRET') or os.getenv('APCA_API_SECRET_KEY')


# ─── Bar fetching (reuses Alpaca like TimesFMForecaster) ─────────────────────

def _fetch_daily_bars(symbol: str, lookback_days: int = 200) -> Optional[dict]:
    """
    Fetch daily OHLCV bars from Alpaca for a symbol.
    Returns dict with lists keyed by column name, or None on failure.
    """
    start = (
        datetime.date.today() - datetime.timedelta(days=lookback_days + 30)
    ).isoformat()
    headers = {
        'APCA-API-KEY-ID':     _ALPACA_KEY,
        'APCA-API-SECRET-KEY': _ALPACA_SECRET,
    }

    try:
        if '/' in symbol:
            # Crypto
            r = requests.get(
                'https://data.alpaca.markets/v1beta3/crypto/us/bars',
                params={'symbols': symbol, 'timeframe': '1Day',
                        'start': start, 'limit': lookback_days + 30},
                headers=headers, timeout=10
            )
            raw_bars = r.json().get('bars', {}).get(symbol, [])
        else:
            # Equity
            r = requests.get(
                'https://data.alpaca.markets/v2/stocks/bars',
                params={'symbols': symbol, 'timeframe': '1Day',
                        'start': start, 'feed': 'sip',
                        'adjustment': 'all', 'limit': lookback_days + 30},
                headers=headers, timeout=10
            )
            raw_bars = r.json().get('bars', {}).get(symbol, [])

        if not raw_bars:
            logger.warning(f'[KRONOS] No bars returned for {symbol}')
            return None

        # Keep last lookback_days bars, sorted by time
        raw_bars = sorted(raw_bars, key=lambda b: b['t'])[-lookback_days:]

        result = {
            'timestamps': [b['t'] for b in raw_bars],
            'open':       [float(b['o']) for b in raw_bars],
            'high':       [float(b['h']) for b in raw_bars],
            'low':        [float(b['l']) for b in raw_bars],
            'close':      [float(b['c']) for b in raw_bars],
            'volume':     [float(b['v']) for b in raw_bars],
        }
        logger.info(f'[KRONOS] Fetched {len(raw_bars)} bars for {symbol}')
        return result

    except Exception as exc:
        logger.error(f'[KRONOS] Bar fetch error for {symbol}: {exc}')
        return None


# ─── Subprocess inference bridge ──────────────────────────────────────────────

_KRONOS_INFERENCE_SCRIPT = '''
import sys, json, os
sys.path.insert(0, '{repo}')

import pandas as pd
import numpy as np
from model.kronos import KronosTokenizer, Kronos, KronosPredictor

# ── Load input ────────────────────────────────────────────────────
with open('{input_path}') as f:
    payload = json.load(f)

bars      = payload['bars']
pred_len  = payload['pred_len']
tok_path  = payload['tokenizer_path']
mod_path  = payload['model_path']
max_ctx   = payload['max_context']
variant   = payload['variant']
sc        = payload['sample_count']

df = pd.DataFrame(bars)
df['timestamps'] = pd.to_datetime(df['timestamps'])
df = df.sort_values('timestamps').reset_index(drop=True)

# ── Build future timestamps (daily freq) ──────────────────────────
last_ts    = df['timestamps'].iloc[-1]
y_timestamp = pd.Series(pd.date_range(start=last_ts, periods=pred_len + 1, freq='B')[1:])
x_timestamp = df['timestamps'].reset_index(drop=True)

# ── Prepare feature DataFrame ─────────────────────────────────────
feat_df = df[['open', 'high', 'low', 'close', 'volume']].copy()

# ── Load model + tokenizer from local path ────────────────────────
tokenizer = KronosTokenizer.from_pretrained(tok_path)
model     = Kronos.from_pretrained(mod_path)
predictor = KronosPredictor(model, tokenizer, max_context=max_ctx)

# ── Run prediction ─────────────────────────────────────────────────
pred_df = predictor.predict(
    df           = feat_df,
    x_timestamp  = x_timestamp,
    y_timestamp  = y_timestamp,
    pred_len     = pred_len,
    T            = 1.0,
    top_k        = 0,
    top_p        = 0.9,
    sample_count = sc,
    verbose      = False,
)

# ── Compute directional signal ─────────────────────────────────────
last_close  = float(df['close'].iloc[-1])
pred_closes = pred_df['close'].tolist()
first_pred  = pred_closes[0] if pred_closes else last_close
pct_change  = (first_pred - last_close) / last_close * 100.0

result = {{
    'direction':       'UP' if pct_change > 0 else 'DOWN',
    'pct_change':      round(pct_change, 4),
    'pred_closes':     [round(c, 6) for c in pred_closes],
    'last_close':      last_close,
    'variant':         variant,
    'sample_count':    sc,
    'bars_used':       len(df),
}}
with open('{output_path}', 'w') as f:
    json.dump(result, f)
print('KRONOS_OK')
'''


def _run_kronos_subprocess(
    bars:      dict,
    pred_len:  int,
    variant:   str = DEFAULT_MODEL,
    timeout:   int = 180,
) -> Optional[dict]:
    """
    Serialize bars to a temp JSON file, run Kronos inference in
    /home/k2/kronos-venv (separate Python process), read result back.
    """
    cfg = MODEL_CONFIG.get(variant, MODEL_CONFIG['mini'])

    # Verify model weights exist before spawning subprocess
    if not os.path.isdir(cfg['model_path']):
        logger.error(f'[KRONOS] Model path missing: {cfg["model_path"]} — run model download first')
        return None
    if not os.path.isdir(cfg['tokenizer_path']):
        logger.error(f'[KRONOS] Tokenizer path missing: {cfg["tokenizer_path"]} — run model download first')
        return None

    tmp_dir = tempfile.mkdtemp(prefix='kronos_')
    input_path  = os.path.join(tmp_dir, 'input.json')
    output_path = os.path.join(tmp_dir, 'output.json')
    script_path = os.path.join(tmp_dir, 'infer.py')

    payload = {
        'bars':           bars,
        'pred_len':       pred_len,
        'tokenizer_path': cfg['tokenizer_path'],
        'model_path':     cfg['model_path'],
        'max_context':    cfg['max_context'],
        'variant':        variant,
        'sample_count':   6,   # average 6 samples — good balance speed/stability on CPU
    }
    with open(input_path, 'w') as f:
        json.dump(payload, f, default=str)

    script_src = _KRONOS_INFERENCE_SCRIPT.format(
        repo=KRONOS_REPO,
        input_path=input_path,
        output_path=output_path,
    )
    with open(script_path, 'w') as f:
        f.write(script_src)

    try:
        proc = subprocess.run(
            [KRONOS_VENV_PYTHON, script_path],
            capture_output=True, text=True, timeout=timeout
        )
        if 'KRONOS_OK' in proc.stdout and os.path.exists(output_path):
            with open(output_path) as f:
                return json.load(f)
        else:
            stderr_tail = proc.stderr[-600:] if proc.stderr else '(no stderr)'
            logger.error(f'[KRONOS] Subprocess failed:\n{stderr_tail}')
            return None

    except subprocess.TimeoutExpired:
        logger.error(f'[KRONOS] Subprocess timed out after {timeout}s')
        return None
    except Exception as exc:
        logger.error(f'[KRONOS] Subprocess exception: {exc}')
        return None
    finally:
        import shutil
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ─── Public API (mirrors TimesFMForecaster interface) ─────────────────────────

def get_kronos_forecast(
    symbol:  str,
    pred_len: int = 5,
    variant:  str = DEFAULT_MODEL,
) -> dict:
    """
    Main entry — mirrors TimesFMForecaster.forecast() return shape.

    Returns::
        {
          'symbol':       str,
          'direction':    'UP' | 'DOWN' | 'NEUTRAL',
          'pct_change':   float,
          'pred_closes':  list[float],
          'last_close':   float | None,
          'model':        str,           # e.g. 'Kronos-mini'
          'available':    bool,
          'error':        str | None,
          # Compatibility keys for TimesFMForecaster consumers:
          'forecast_direction':   str,
          'forecast_pct_change':  float,
          'confidence':           float,
          'method':               str,
        }
    """
    logger.info(f'[KRONOS] Forecasting {symbol} (Kronos-{variant}, pred_len={pred_len})')

    bars = _fetch_daily_bars(symbol, lookback_days=min(200, MODEL_CONFIG[variant]['max_context']))
    if bars is None or len(bars.get('timestamps', [])) < 30:
        return _error_result(symbol, variant, 'Insufficient bar data')

    result = _run_kronos_subprocess(bars, pred_len, variant)
    if result is None:
        return _error_result(symbol, variant, 'Kronos inference failed')

    direction  = result['direction']
    pct_change = result['pct_change']

    logger.info(
        f'[KRONOS] {symbol}: {direction} {pct_change:+.2f}% '
        f'(Kronos-{variant}, {result.get("sample_count", "?")} samples, '
        f'{result.get("bars_used", "?")} bars)'
    )

    return {
        'symbol':       symbol,
        'direction':    direction,
        'pct_change':   pct_change,
        'pred_closes':  result.get('pred_closes', []),
        'last_close':   result.get('last_close'),
        'model':        f'Kronos-{variant}',
        'available':    True,
        'error':        None,
        # TimesFMForecaster-compatible aliases
        'forecast_direction':  direction,
        'forecast_pct_change': pct_change,
        'confidence':          0.75,   # conservative until back-tested
        'method':              f'kronos-{variant}',
    }


def get_kronos_forecast_batch(
    symbols: list,
    pred_len: int = 5,
    variant:  str = DEFAULT_MODEL,
) -> dict:
    """Batch forecast. Returns dict keyed by symbol."""
    return {sym: get_kronos_forecast(sym, pred_len, variant) for sym in symbols}


def compare_with_timesfm(symbol: str, variant: str = DEFAULT_MODEL) -> dict:
    """
    Run Kronos AND TimesFM on the same symbol and compare.
    Used for validation before deciding on swap vs ensemble.

    Returns::
        {
          'symbol':           str,
          'kronos':           { direction, pct_change, model },
          'timesfm':          { direction, pct_change },
          'agree':            bool,
          'agreement_signal': 'STRONG' | 'CONFLICTED',
        }
    """
    kronos = get_kronos_forecast(symbol, variant=variant)

    try:
        from agents.timesfm_forecaster import TimesFMForecaster
        tfm    = TimesFMForecaster()
        asset  = 'crypto' if '/' in symbol else 'equities'
        tfm_fc = tfm.forecast(symbol, asset_class=asset) or {}
        tfm_dir = tfm_fc.get('forecast_direction', 'NEUTRAL')
        tfm_pct = tfm_fc.get('forecast_pct_change', 0.0)
    except Exception as exc:
        logger.warning(f'[KRONOS] Linear baseline comparison failed: {exc}')
        tfm_dir = 'UNAVAILABLE'
        tfm_pct = 0.0

    agree = (kronos['direction'] == tfm_dir) and tfm_dir not in ('NEUTRAL', 'UNAVAILABLE')

    comparison = {
        'symbol':  symbol,
        'kronos':  {
            'direction':  kronos['direction'],
            'pct_change': kronos['pct_change'],
            'model':      kronos['model'],
        },
        'timesfm': {
            'direction':  tfm_dir,
            'pct_change': tfm_pct,
        },
        'agree':            agree,
        'agreement_signal': 'STRONG' if agree else 'CONFLICTED',
    }

    logger.info(
        f'[KRONOS vs Linear Baseline] {symbol}: '
        f'Kronos={kronos["direction"]} {kronos["pct_change"]:+.2f}% | '
        f'Linear Baseline={tfm_dir} {tfm_pct:+.2f}% | '
        f'{"✅ AGREE" if agree else "⚠️ CONFLICT"}'
    )
    return comparison


def _error_result(symbol: str, variant: str, error: str) -> dict:
    return {
        'symbol':              symbol,
        'direction':           'NEUTRAL',
        'pct_change':          0.0,
        'pred_closes':         [],
        'last_close':          None,
        'model':               f'Kronos-{variant}',
        'available':           False,
        'error':               error,
        'forecast_direction':  'NEUTRAL',
        'forecast_pct_change': 0.0,
        'confidence':          0.0,
        'method':              f'kronos-{variant}',
    }
