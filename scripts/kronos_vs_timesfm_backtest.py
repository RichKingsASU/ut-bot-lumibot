"""
Kronos vs TimesFM — Directional Accuracy Walk-Forward Backtest.

For each symbol, walks forward over the last N trading days, asks Kronos
to predict "next day up or down", then checks against actual. Computes
accuracy vs random-walk baseline.

Usage:
    python3 scripts/kronos_vs_timesfm_backtest.py [--symbols SPY QQQ ETH/USD]
"""
import sys, os, json, argparse, datetime, logging
sys.path.insert(0, '/home/k2/ut-bot-lumibot')

from dotenv import load_dotenv
load_dotenv('/home/k2/ut-bot-lumibot/.env')

import requests
import pandas as pd

from agents.kronos_forecaster import get_kronos_forecast

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger('backtest')

DEFAULT_SYMBOLS = ['SPY', 'QQQ', 'ETH/USD', 'BTC/USD']
TEST_WINDOW     = 20   # number of days to walk forward over
LOOKBACK        = 120  # bars of history to feed each day

_KEY    = os.getenv('ALPACA_API_KEY') or os.getenv('APCA_API_KEY_ID')
_SECRET = os.getenv('ALPACA_API_SECRET') or os.getenv('APCA_API_SECRET_KEY')


def fetch_bars(symbol: str, days: int = LOOKBACK + TEST_WINDOW + 10) -> pd.DataFrame:
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    headers = {'APCA-API-KEY-ID': _KEY, 'APCA-API-SECRET-KEY': _SECRET}

    if '/' in symbol:
        r = requests.get(
            'https://data.alpaca.markets/v1beta3/crypto/us/bars',
            params={'symbols': symbol, 'timeframe': '1Day', 'start': start, 'limit': days},
            headers=headers, timeout=10
        )
        raw = r.json().get('bars', {}).get(symbol, [])
    else:
        r = requests.get(
            'https://data.alpaca.markets/v2/stocks/bars',
            params={'symbols': symbol, 'timeframe': '1Day', 'start': start,
                    'feed': 'sip', 'adjustment': 'all', 'limit': days},
            headers=headers, timeout=10
        )
        raw = r.json().get('bars', {}).get(symbol, [])

    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw).rename(columns={'t': 'ts', 'o': 'open', 'h': 'high',
                                            'l': 'low',  'c': 'close', 'v': 'volume'})
    df['ts'] = pd.to_datetime(df['ts'])
    return df.sort_values('ts').reset_index(drop=True)


def directional_accuracy(preds: list, actuals: list) -> float:
    if not preds:
        return 0.0
    return sum(1 for p, a in zip(preds, actuals) if p == a) / len(preds)


def run_backtest(symbol: str) -> dict:
    print(f'\n📊 {symbol}', flush=True)
    all_bars = fetch_bars(symbol)

    if len(all_bars) < LOOKBACK + TEST_WINDOW + 2:
        print(f'  ⚠️  Insufficient data ({len(all_bars)} bars)', flush=True)
        return {'symbol': symbol, 'error': f'only {len(all_bars)} bars'}

    kronos_preds  = []
    actual_dirs   = []

    # Walk-forward: for day i predict day i+1
    start_idx = len(all_bars) - TEST_WINDOW - 1
    for i in range(start_idx, start_idx + TEST_WINDOW):
        hist = all_bars.iloc[max(0, i - LOOKBACK): i]
        actual_next  = all_bars.iloc[i + 1]
        actual_close = float(actual_next['close'])
        prev_close   = float(hist['close'].iloc[-1])
        actual_dir   = 'UP' if actual_close > prev_close else 'DOWN'
        actual_dirs.append(actual_dir)

        # Build bars dict from historical slice (don't call live Alpaca for each step;
        # use the already-fetched data to simulate live state)
        bars_dict = {
            'timestamps': hist['ts'].dt.isoformat().tolist(),
            'open':       hist['open'].tolist(),
            'high':       hist['high'].tolist(),
            'low':        hist['low'].tolist(),
            'close':      hist['close'].tolist(),
            'volume':     hist['volume'].tolist(),
        }

        # Import the subprocess runner directly
        from agents.kronos_forecaster import _run_kronos_subprocess
        res = _run_kronos_subprocess(bars_dict, pred_len=1, variant='mini', timeout=180)
        if res:
            kronos_preds.append(res['direction'])
        else:
            # Model not available yet — record as NEUTRAL (miss)
            kronos_preds.append('NEUTRAL')

        day_label = all_bars.iloc[i]['ts'].strftime('%Y-%m-%d')
        print(
            f'  Day {i - start_idx + 1:2d}/{TEST_WINDOW} {day_label} '
            f'| actual={actual_dir:4s} | kronos={kronos_preds[-1]:7s}',
            flush=True
        )

    acc = directional_accuracy(
        [p for p in kronos_preds if p != 'NEUTRAL'],
        [a for p, a in zip(kronos_preds, actual_dirs) if p != 'NEUTRAL']
    )
    n_valid    = sum(1 for p in kronos_preds if p != 'NEUTRAL')
    pct_up     = sum(1 for d in actual_dirs if d == 'UP') / len(actual_dirs)
    baseline   = max(pct_up, 1 - pct_up)   # naive always-up/down baseline
    edge       = acc - baseline

    print(f'\n  ── Results for {symbol} ──')
    print(f'  Valid predictions : {n_valid}/{TEST_WINDOW}')
    print(f'  Kronos accuracy   : {acc:.1%}')
    print(f'  Baseline (naive)  : {baseline:.1%}')
    print(f'  Edge over baseline: {edge:+.1%}')

    return {
        'symbol':         symbol,
        'kronos_accuracy': acc,
        'baseline':       baseline,
        'edge':           edge,
        'n_valid':        n_valid,
        'total':          TEST_WINDOW,
        'actual_up_pct':  pct_up,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', nargs='+', default=DEFAULT_SYMBOLS)
    args = parser.parse_args()

    print('=' * 60)
    print('KRONOS vs TimesFM — Directional Accuracy Backtest')
    print(f'Walk-forward window: {TEST_WINDOW} days | lookback: {LOOKBACK} bars')
    print('=' * 60)

    results = {}
    for sym in args.symbols:
        try:
            results[sym] = run_backtest(sym)
        except Exception as exc:
            print(f'  ERROR: {exc}', flush=True)
            results[sym] = {'symbol': sym, 'error': str(exc)}

    print('\n' + '=' * 60)
    print('FINAL SUMMARY')
    print('=' * 60)
    for sym, r in results.items():
        if 'error' in r:
            print(f'{sym:12s} ERROR: {r["error"]}')
        else:
            flag = '✅' if r['edge'] > 0 else '❌'
            print(
                f'{flag} {sym:12s} '
                f'Kronos={r["kronos_accuracy"]:.1%} | '
                f'Baseline={r["baseline"]:.1%} | '
                f'Edge={r["edge"]:+.1%} | '
                f'n={r["n_valid"]}'
            )

    out_path = '/home/k2/ut-bot-lumibot/logs/kronos_backtest_results.json'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'\nResults → {out_path}')


if __name__ == '__main__':
    main()
