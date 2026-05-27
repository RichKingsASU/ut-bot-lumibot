import os
import httpx
import pytz
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv('/home/k2/ut-bot-lumibot/.env')

MACRO_EVENT_DATES_2026 = [
    # Fed meetings
    '2026-01-28', '2026-01-29',
    '2026-03-18', '2026-03-19',
    '2026-05-06', '2026-05-07',
    '2026-06-17', '2026-06-18',
    '2026-07-29', '2026-07-30',
    '2026-09-16', '2026-09-17',
    '2026-10-28', '2026-10-29',
    '2026-12-09', '2026-12-10',
    # CPI releases (approx 2nd week)
    '2026-01-13', '2026-02-10', '2026-03-10', '2026-04-14',
    '2026-05-12', '2026-06-09', '2026-07-14', '2026-08-11',
    '2026-09-15', '2026-10-13', '2026-11-10', '2026-12-08',
    # Jobs reports (approx 1st Friday)
    '2026-01-09', '2026-02-06', '2026-03-06', '2026-04-03',
    '2026-05-01', '2026-06-05', '2026-07-03', '2026-08-07',
    '2026-09-04', '2026-10-02', '2026-11-06', '2026-12-04'
]

class ExecutionFilter:

    def __init__(self):
        self.alpaca_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_secret = os.getenv('ALPACA_API_SECRET')
        self.alpaca_base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        self.headers = {
            'APCA-API-KEY-ID': self.alpaca_key,
            'APCA-API-SECRET-KEY': self.alpaca_secret
        }

    def is_optimal_trading_hours(self) -> dict:
        ET = pytz.timezone('America/New_York')
        now = ET.localize(datetime.now())
        hour = now.hour
        minute = now.minute
        time_decimal = hour + minute/60

        optimal = 10.0 <= time_decimal <= 15.5
        reason = ''
        if time_decimal < 9.5:
            reason = 'Pre-market — avoid'
        elif time_decimal < 10.0:
            reason = 'Opening 30min — high spread, avoid'
        elif time_decimal > 15.5:
            reason = 'Closing 30min — manipulation risk'
            optimal = False
        elif time_decimal > 16.0:
            reason = 'After-hours — avoid'
            optimal = False
        else:
            reason = 'Optimal trading window'

        return {
            'optimal': optimal,
            'reason': reason,
            'time_et': now.strftime('%H:%M ET')
        }

    def is_macro_event_day(self, lookahead_days: int = 1) -> dict:
        import datetime as dt
        today = dt.date.today()
        
        is_event_day = False
        event_name = ""
        event_date = ""
        
        for i in range(lookahead_days + 1):
            target_date = today + dt.timedelta(days=i)
            target_str = target_date.strftime('%Y-%m-%d')
            if target_str in MACRO_EVENT_DATES_2026:
                is_event_day = True
                event_date = target_str
                event_name = "Macro Event (Fed/CPI/NFP)"
                break
                
        recommendation = 'SKIP' if is_event_day else 'TRADE'
        return {
            'is_event_day': is_event_day,
            'event_name': event_name,
            'event_date': event_date,
            'recommendation': recommendation
        }

    def check_gap(self, symbol: str = 'SPY') -> dict:
        url = f"{self.alpaca_base}/v2/stocks/{symbol}/quotes/latest"
        bars_url = f"{self.alpaca_base}/v2/stocks/{symbol}/bars"
        
        gap_pct = 0.0
        gap_direction = 'FLAT'
        excessive_gap = False
        
        try:
            # Need previous close, using bars for that.
            params = {
                "timeframe": "1Day",
                "limit": 2
            }
            resp = httpx.get(bars_url, headers=self.headers, params=params, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                bars = data.get("bars", [])
                if len(bars) >= 2:
                    prev_close = bars[-2].get("c", 0.0)
                    current = bars[-1].get("c", prev_close)
                    
                    if prev_close > 0:
                        gap_pct = (current - prev_close) / prev_close
                        
                        if gap_pct > 0.001:
                            gap_direction = 'UP'
                        elif gap_pct < -0.001:
                            gap_direction = 'DOWN'
                            
                        excessive_gap = abs(gap_pct) > 0.01
        except Exception as e:
            pass
            
        return {
            'gap_pct': float(gap_pct),
            'gap_direction': gap_direction,
            'excessive_gap': excessive_gap,
            'recommendation': 'SKIP' if excessive_gap else 'TRADE'
        }

    def full_execution_check(self, symbol: str = 'SPY') -> dict:
        hours_check = self.is_optimal_trading_hours()
        macro_check = self.is_macro_event_day()
        gap_check = self.check_gap(symbol)
        
        approved = True
        reasons = []
        
        if not hours_check['optimal']:
            approved = False
            reasons.append(hours_check['reason'])
            
        if macro_check['is_event_day']:
            approved = False
            reasons.append(f"Macro event on {macro_check['event_date']}")
            
        if gap_check['excessive_gap']:
            approved = False
            reasons.append(f"Excessive gap ({gap_check['gap_pct']:.2%})")
            
        if approved:
            recommendation = 'TRADE'
        else:
            recommendation = 'SKIP'
            
        return {
            'approved': approved,
            'reasons': reasons,
            'recommendation': recommendation
        }
