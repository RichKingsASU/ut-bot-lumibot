import os, httpx, datetime, logging
from zoneinfo import ZoneInfo
from pydantic import ValidationError
from agents.risk_models import MarketDataFreshnessModel

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

def is_market_hours() -> bool:
    now = datetime.datetime.now(ET)
    if now.weekday() >= 5:
        return False
    open_ = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_ = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_ <= now <= close_

def validate_market_freshness(symbol: str = 'SPY', asset_class: str = 'equities') -> bool:
    ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
    ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')
    market_hours = is_market_hours() if asset_class == 'equities' else False
    try:
        endpoint = 'https://data.alpaca.markets/v2/stocks/bars/latest'
        params = {'symbols': symbol, 'feed': 'iex'}
        r = httpx.get(endpoint, params=params,
            headers={'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask}, timeout=5)
        bar = r.json().get('bars', {}).get(symbol, {})
        if not bar:
            logger.warning(f"[FRESHNESS] No bar data for {symbol}")
            return not market_hours
        last_bar = datetime.datetime.fromisoformat(bar['t'].replace('Z', '+00:00'))
        MarketDataFreshnessModel(
            symbol=symbol,
            last_bar_timestamp=last_bar,
            current_time=datetime.datetime.now(datetime.timezone.utc),
            is_market_hours=market_hours
        )
        return True
    except ValidationError as e:
        logger.error(f"[FRESHNESS] {e} — HALTING CYCLE")
        return False
    except Exception as e:
        logger.warning(f"[FRESHNESS] Check failed: {e}")
        return not market_hours
