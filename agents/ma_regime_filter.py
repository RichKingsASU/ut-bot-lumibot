"""
200-day Moving Average regime filter.
Simple, academically validated secondary regime gate for equities.

Rule: SPY below 200-day MA = bear market posture.
  - Block BUY signals (allow HOLD/SELL)
  - OR reduce position size by 50%

Used alongside HMM regime — provides a longer-term context
that HMM's short-term signals may miss.
"""
import os, httpx, datetime, logging
from typing import Optional

logger = logging.getLogger(__name__)

def get_spy_200day_ma() -> dict:
    """
    Fetches 201 days of SPY daily bars and computes the 200-day SMA.
    Returns current price, 200-day MA, and whether price is above/below.
    """
    ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
    ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')
    headers = {'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask}

    start = (datetime.date.today() - datetime.timedelta(days=350)).isoformat()

    try:
        r = httpx.get(
            'https://data.alpaca.markets/v2/stocks/bars',
            params={
                'symbols': 'SPY',
                'timeframe': '1Day',
                'start': start,
                'feed': 'sip',
                'adjustment': 'all',
                'limit': 250
            },
            headers=headers,
            timeout=10
        )
        bars = r.json().get('bars', {}).get('SPY', [])

        if len(bars) < 200:
            logger.warning(f"[200MA] Insufficient bars: {len(bars)} (need 200)")
            return {
                'available': False,
                'error': f'Only {len(bars)} bars available',
                'regime': 'UNKNOWN',
                'above_200ma': True  # Default to allowing trades
            }

        closes = [b.get('c', 0) for b in bars]
        ma_200 = sum(closes[-200:]) / 200
        current_price = closes[-1]
        above_ma = current_price > ma_200
        pct_from_ma = ((current_price - ma_200) / ma_200) * 100

        regime = 'BULL_MARKET' if above_ma else 'BEAR_MARKET'
        logger.info(
            f"[200MA] SPY={current_price:.2f} vs 200MA={ma_200:.2f} "
            f"({pct_from_ma:+.1f}%) — {regime}"
        )

        return {
            'available': True,
            'current_price': current_price,
            'ma_200': round(ma_200, 2),
            'pct_from_ma': round(pct_from_ma, 2),
            'above_200ma': above_ma,
            'regime': regime,
            'signal': (
                'NORMAL — price above 200MA, all signals active'
                if above_ma else
                f'DEFENSIVE — price {abs(pct_from_ma):.1f}% below 200MA. '
                f'Blocking BUY signals, reducing position sizes 50%.'
            )
        }

    except Exception as e:
        logger.warning(f"[200MA] Computation error: {e}")
        return {
            'available': False,
            'error': str(e),
            'regime': 'UNKNOWN',
            'above_200ma': True  # Default to allowing trades on error
        }

def apply_ma_filter(signal: dict, ma_data: dict) -> dict:
    """
    Applies the 200MA filter to a signal dict.
    If below 200MA: converts BUY to HOLD, halves Kelly size.
    Returns modified signal.
    """
    if not ma_data.get('available') or ma_data.get('above_200ma', True):
        return signal  # No change needed

    # Below 200MA — apply defensive posture
    modified = signal.copy()

    if signal.get('action') == 'BUY':
        modified['action'] = 'HOLD'
        modified['reasoning'] = (
            signal.get('reasoning', '') +
            f" | 200MA FILTER: BUY blocked — SPY is "
            f"{abs(ma_data.get('pct_from_ma', 0)):.1f}% below 200-day MA "
            f"(bear market posture)"
        )
        # Halve Kelly size as additional caution
        if modified.get('kelly_position_value'):
            modified['kelly_position_value'] = modified['kelly_position_value'] * 0.5

        logger.info(
            f"[200MA] BUY signal for {signal.get('symbol')} "
            f"converted to HOLD — below 200MA"
        )

    return modified
