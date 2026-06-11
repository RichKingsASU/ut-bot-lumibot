from datetime import datetime
import pytz
from strategies.ut_bot import _daily_bar_is_stale

ET = pytz.timezone("America/New_York")

def test_fresh_today():        # today's bar -> fresh
    now = ET.localize(datetime(2026, 6, 11, 12, 0, 0))
    assert _daily_bar_is_stale(ET.localize(datetime(2026, 6, 11, 0, 0, 0)), now, 5) == (False, 0)

def test_long_weekend_fresh(): # Fri bar, Mon now (3 days) -> fresh
    now = ET.localize(datetime(2026, 6, 8, 9, 30, 0))
    assert _daily_bar_is_stale(ET.localize(datetime(2026, 6, 5, 0, 0, 0)), now, 5)[0] is False

def test_genuinely_stale():    # 10 days old -> stale (feed broken)
    now = ET.localize(datetime(2026, 6, 11, 12, 0, 0))
    stale, age = _daily_bar_is_stale(ET.localize(datetime(2026, 6, 1, 0, 0, 0)), now, 5)
    assert stale is True and age == 10
