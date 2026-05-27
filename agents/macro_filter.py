import os
from datetime import datetime, date, timedelta
import httpx
import pytz
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')

KNOWN_MACRO_EVENTS_2026 = {
    '2026-01-28': 'Fed Meeting',
    '2026-01-29': 'Fed Meeting',
    '2026-03-18': 'Fed Meeting',
    '2026-03-19': 'Fed Meeting',
    '2026-05-06': 'Fed Meeting',
    '2026-05-07': 'Fed Meeting',
    '2026-06-17': 'Fed Meeting',
    '2026-06-18': 'Fed Meeting',
    '2026-07-29': 'Fed Meeting',
    '2026-07-30': 'Fed Meeting',
    '2026-09-16': 'Fed Meeting',
    '2026-09-17': 'Fed Meeting',
    '2026-10-28': 'Fed Meeting',
    '2026-10-29': 'Fed Meeting',
    '2026-12-09': 'Fed Meeting',
    '2026-12-10': 'Fed Meeting',
    '2026-01-13': 'CPI Release',
    '2026-02-10': 'CPI Release',
    '2026-03-10': 'CPI Release',
    '2026-04-14': 'CPI Release',
    '2026-05-12': 'CPI Release',
    '2026-06-09': 'CPI Release',
    '2026-07-14': 'CPI Release',
    '2026-08-11': 'CPI Release',
    '2026-09-15': 'CPI Release',
    '2026-10-13': 'CPI Release',
    '2026-11-10': 'CPI Release',
    '2026-12-08': 'CPI Release',
    '2026-01-09': 'Jobs Report',
    '2026-02-06': 'Jobs Report',
    '2026-03-06': 'Jobs Report',
    '2026-04-03': 'Jobs Report',
    '2026-05-01': 'Jobs Report',
    '2026-06-05': 'Jobs Report',
    '2026-07-03': 'Jobs Report',
    '2026-08-07': 'Jobs Report',
    '2026-09-04': 'Jobs Report',
    '2026-10-02': 'Jobs Report',
    '2026-11-06': 'Jobs Report',
    '2026-12-04': 'Jobs Report'
}

class MacroFilter:
    def __init__(self):
        self.alpaca_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_secret = os.getenv('ALPACA_API_SECRET')
        self.alpaca_base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

    def get_upcoming_events(self, days_ahead: int = 2) -> list:
        today = date.today()
        upcoming = []
        for i in range(days_ahead + 1):
            target_date = today + timedelta(days=i)
            target_str = target_date.strftime('%Y-%m-%d')
            if target_str in KNOWN_MACRO_EVENTS_2026:
                upcoming.append({
                    'date': target_str,
                    'event_name': KNOWN_MACRO_EVENTS_2026[target_str],
                    'days_until': i
                })
        return upcoming

    def should_trade(self, symbol: str = 'SPY') -> dict:
        upcoming = self.get_upcoming_events(days_ahead=1)
        if upcoming:
            return {
                'approved': False,
                'reason': f'Macro event tomorrow: {upcoming[0]["event_name"]}',
                'events': upcoming
            }
        return {'approved': True, 'reason': 'No macro events', 'events': []}

    def get_earnings_dates(self, symbols: list) -> dict:
        today = date.today()
        end_date = today + timedelta(days=30)
        
        url = f"{self.alpaca_base}/v1beta1/news"
        params = {
            "symbols": ",".join(symbols),
            "start": today.strftime('%Y-%m-%dT00:00:00Z'),
            "end": end_date.strftime('%Y-%m-%dT00:00:00Z')
        }
        headers = {
            'APCA-API-KEY-ID': self.alpaca_key,
            'APCA-API-SECRET-KEY': self.alpaca_secret
        }
        
        earnings_dates = {}
        try:
            resp = httpx.get(url, headers=headers, params=params, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                news = data.get('news', [])
                for item in news:
                    headline = item.get('headline', '').lower()
                    if 'earnings' in headline:
                        for sym in item.get('symbols', []):
                            if sym in symbols and sym not in earnings_dates:
                                earnings_dates[sym] = item.get('created_at')
        except Exception:
            pass
            
        return earnings_dates
