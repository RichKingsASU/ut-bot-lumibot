"""
Post-Earnings Announcement Drift (PEAD) signal.
Detects recent earnings surprises and returns a modifier
for the debate agent prompts.

Academic basis: PEAD is documented in Fama (1998), Bernard & Thomas (1989).
SUE > 1.0 with volume confirmation = bullish drift expected 5-20 days.
SUE < -1.0 with volume confirmation = bearish drift expected 5-20 days.
"""
import os, httpx, datetime, logging
from typing import Optional

logger = logging.getLogger(__name__)

EQUITY_SYMBOLS = ['SPY', 'IWM', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'META', 'GOOGL']

def get_recent_earnings_news(symbol: str, days_back: int = 20) -> list:
    """
    Fetches recent news for a symbol and filters for earnings-related articles.
    Uses Alpaca news API + our Supabase news_articles table.
    """
    ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
    ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')

    since = (datetime.datetime.utcnow() - datetime.timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%SZ')

    try:
        r = httpx.get(
            'https://data.alpaca.markets/v1beta1/news',
            params={
                'symbols': symbol,
                'start': since,
                'limit': 50,
                'include_content': 'false'
            },
            headers={'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask},
            timeout=5
        )
        if r.status_code == 200:
            news = r.json().get('news', [])
            # Filter for earnings-related headlines
            earnings_keywords = [
                'earnings', 'eps', 'quarterly', 'revenue', 'profit',
                'beat', 'miss', 'guidance', 'q1', 'q2', 'q3', 'q4',
                'results', 'reports'
            ]
            return [
                n for n in news
                if any(kw in n.get('headline', '').lower()
                       for kw in earnings_keywords)
            ]
        return []
    except Exception as e:
        logger.warning(f"[PEAD] News fetch error for {symbol}: {e}")
        return []

def get_volume_spike(symbol: str) -> Optional[float]:
    """
    Returns the ratio of today's volume to 30-day average.
    > 2.0 = significant institutional attention (PEAD confirmation).
    """
    ak = os.getenv('APCA_API_KEY_ID') or os.getenv('ALPACA_API_KEY')
    ask = os.getenv('APCA_API_SECRET_KEY') or os.getenv('ALPACA_API_SECRET')
    headers = {'APCA-API-KEY-ID': ak, 'APCA-API-SECRET-KEY': ask}

    try:
        # Get last 31 days of daily bars
        start = (datetime.date.today() - datetime.timedelta(days=31)).isoformat()
        r = httpx.get(
            f'https://data.alpaca.markets/v2/stocks/bars',
            params={
                'symbols': symbol,
                'timeframe': '1Day',
                'start': start,
                'feed': 'sip',
                'adjustment': 'all'
            },
            headers=headers,
            timeout=5
        )
        bars = r.json().get('bars', {}).get(symbol, [])
        if len(bars) < 2:
            return None

        volumes = [b.get('v', 0) for b in bars]
        avg_volume = sum(volumes[:-1]) / max(len(volumes) - 1, 1)  # 30-day avg
        today_volume = volumes[-1]

        return today_volume / avg_volume if avg_volume > 0 else None
    except Exception as e:
        logger.warning(f"[PEAD] Volume fetch error for {symbol}: {e}")
        return None

def get_pead_signal(symbol: str) -> dict:
    """
    Returns a PEAD signal modifier for the given symbol.
    Call this once per cycle per symbol and pass to debate agents.
    """
    earnings_news = get_recent_earnings_news(symbol)
    volume_ratio = get_volume_spike(symbol)

    if not earnings_news:
        return {
            'has_earnings_event': False,
            'signal': 'NEUTRAL',
            'modifier': 0.0,
            'description': 'No recent earnings event detected',
            'volume_ratio': volume_ratio
        }

    # Use our existing FinBERT scores from Supabase for these articles
    # Check news_articles table for scored versions of recent earnings articles
    import httpx as _h
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    supabase_headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

    try:
        # Get recent scored articles related to this symbol
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=20)).isoformat()
        r = _h.get(
            f'{url}/rest/v1/news_articles',
            headers=supabase_headers,
            params={
                'order': 'published_at.desc',
                'limit': '10',
                'published_at': f'gte.{since}'
            },
            timeout=5
        )
        articles = r.json() if r.status_code == 200 else []

        # Filter articles mentioning this symbol
        symbol_clean = symbol.replace('/USD', '').replace('/', '')
        relevant = [
            a for a in articles
            if symbol_clean.lower() in str(a.get('title', '')).lower()
            or symbol_clean.lower() in str(a.get('summary', '')).lower()
        ]

        if not relevant:
            return {
                'has_earnings_event': True,
                'signal': 'UNSCORED',
                'modifier': 0.0,
                'description': f'Earnings event detected but not yet scored',
                'volume_ratio': volume_ratio,
                'articles_found': len(earnings_news)
            }

        # Average the sentiment scores
        scores = [
            float(a.get('score', a.get('finbert_score', 0)))
            for a in relevant
            if a.get('score') or a.get('finbert_score')
        ]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        vol_confirmed = volume_ratio and volume_ratio > 2.0

        # Determine PEAD signal
        if avg_score > 0.3 and vol_confirmed:
            signal = 'BULLISH_DRIFT'
            modifier = 15.0  # Add 15 points to bull score
            desc = (f'PEAD: Positive earnings surprise (sentiment={avg_score:.2f}, '
                   f'vol_ratio={volume_ratio:.1f}x). '
                   f'Expect bullish drift 5-20 days.')
        elif avg_score < -0.3 and vol_confirmed:
            signal = 'BEARISH_DRIFT'
            modifier = -15.0  # Add 15 points to bear score
            desc = (f'PEAD: Negative earnings surprise (sentiment={avg_score:.2f}, '
                   f'vol_ratio={volume_ratio:.1f}x). '
                   f'Expect bearish drift 5-20 days.')
        else:
            signal = 'WEAK_PEAD'
            modifier = 0.0
            desc = (f'Earnings detected but signal weak '
                   f'(sentiment={avg_score:.2f}, '
                   f'vol_confirmed={vol_confirmed})')

        logger.info(f"[PEAD] {symbol}: {signal} modifier={modifier:+.1f}")

        return {
            'has_earnings_event': True,
            'signal': signal,
            'modifier': modifier,
            'description': desc,
            'avg_sentiment': avg_score,
            'volume_ratio': volume_ratio,
            'volume_confirmed': vol_confirmed,
            'articles_scored': len(scores)
        }

    except Exception as e:
        logger.warning(f"[PEAD] Signal computation error for {symbol}: {e}")
        return {
            'has_earnings_event': True,
            'signal': 'ERROR',
            'modifier': 0.0,
            'description': f'PEAD computation error: {e}',
            'volume_ratio': volume_ratio
        }
