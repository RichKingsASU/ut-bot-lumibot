"""
Simplified Gamma Exposure (GEX) calculator.
Computes dealer gamma positioning from SPY options chain data.
Used to refine regime context for the debate agents.

GEX interpretation:
  Positive GEX → dealers long gamma → stabilizing market → mean reversion
  Negative GEX → dealers short gamma → accelerating market → trend following
  Near zero    → transition zone → choppy/uncertain → reduce size
"""
import os, httpx, logging, datetime
from typing import Optional

logger = logging.getLogger(__name__)

def fetch_spy_options_chain() -> list:
    """Fetches SPY options chain from Alpaca."""
    ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
    ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')
    headers = {'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask}

    # Get options expiring within 7 days (0DTE to weekly)
    today = datetime.date.today()
    expiry_limit = (today + datetime.timedelta(days=7)).isoformat()

    try:
        r = httpx.get(
            'https://data.alpaca.markets/v1beta1/options/snapshots/SPY',
            params={
                'expiration_date_gte': today.isoformat(),
                'expiration_date_lte': expiry_limit,
                'limit': 200
            },
            headers=headers,
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            snapshots = data.get('snapshots', {})
            return list(snapshots.values())
        else:
            logger.warning(f"[GEX] Options chain fetch failed: {r.status_code}")
            return []
    except Exception as e:
        logger.warning(f"[GEX] Fetch error: {e}")
        return []

def get_spy_price() -> Optional[float]:
    """Gets current SPY price."""
    ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
    ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')
    try:
        r = httpx.get(
            'https://data.alpaca.markets/v2/stocks/bars/latest',
            params={'symbols': 'SPY', 'feed': 'sip'},
            headers={'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask},
            timeout=5
        )
        return r.json().get('bars', {}).get('SPY', {}).get('c')
    except:
        return None

def compute_gex() -> dict:
    """
    Computes simplified Net GEX for SPY.
    Returns dict with gex_value, gex_regime, and interpretation.
    """
    spy_price = get_spy_price()
    if not spy_price:
        return {
            'gex_value': None,
            'gex_regime': 'UNKNOWN',
            'interpretation': 'Cannot compute GEX — SPY price unavailable',
            'available': False
        }

    options = fetch_spy_options_chain()
    if not options:
        return {
            'gex_value': None,
            'gex_regime': 'UNKNOWN',
            'interpretation': 'Cannot compute GEX — options chain unavailable',
            'available': False
        }

    # Filter to ATM options (within 2% of current price)
    atm_range = spy_price * 0.02
    net_gex = 0.0

    for snap in options:
        details = snap.get('details', {})
        greeks = snap.get('greeks', {})
        oi = snap.get('openInterest', 0) or 0
        gamma = greeks.get('gamma', 0) or 0
        strike = details.get('strike_price', 0) or 0
        option_type = details.get('type', '').lower()  # 'call' or 'put'

        if abs(strike - spy_price) > atm_range:
            continue

        # GEX contribution: OI × Gamma × 100 × SpyPrice
        # Calls add positive GEX, Puts subtract (dealers short puts = long gamma)
        contribution = oi * gamma * 100 * spy_price
        if option_type == 'call':
            net_gex += contribution
        elif option_type == 'put':
            net_gex -= contribution

    # Classify GEX regime
    if net_gex > 500_000_000:      # > $500M positive
        regime = 'POSITIVE_GEX'
        interpretation = ('Dealers long gamma — stabilizing market. '
                         'Expect mean reversion. Favor range trades.')
        size_modifier = 0.8  # Reduce size — lower vol expected
    elif net_gex < -200_000_000:   # < -$200M negative
        regime = 'NEGATIVE_GEX'
        interpretation = ('Dealers short gamma — accelerating market. '
                         'Expect trend amplification. Favor breakouts.')
        size_modifier = 1.2  # Increase size — higher vol, trend confirmed
    elif abs(net_gex) < 100_000_000:
        regime = 'TRANSITION_ZONE'
        interpretation = ('Near zero GEX — weak dealer influence. '
                         'Choppy/uncertain. Reduce size or avoid.')
        size_modifier = 0.5  # Reduce size significantly
    else:
        regime = 'NEUTRAL_GEX'
        interpretation = 'Moderate GEX — normal market conditions.'
        size_modifier = 1.0

    logger.info(f"[GEX] Net GEX: ${net_gex/1e6:.1f}M — {regime}")

    return {
        'gex_value': net_gex,
        'gex_value_millions': round(net_gex / 1_000_000, 2),
        'gex_regime': regime,
        'interpretation': interpretation,
        'size_modifier': size_modifier,
        'spy_price': spy_price,
        'options_sampled': len(options),
        'available': True
    }
