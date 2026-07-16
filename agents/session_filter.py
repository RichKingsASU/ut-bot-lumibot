"""
Time-of-day session filter.
Research basis: Zarattini et al. 2024 — profitable equities windows
are 09:30-10:45 ET and 15:00-16:00 ET. Mid-day 11:00-14:00 is churn.
"""
import datetime
import logging
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

def get_session_context() -> dict:
    """
    Returns current session state and allowed actions.
    Called at the start of every orchestrator cycle.
    """
    now = datetime.datetime.now(ET)
    hour = now.hour
    minute = now.minute
    time_decimal = hour + minute / 60.0
    weekday = now.weekday()

    # Weekend — equities market closed
    if weekday >= 5:
        return {
            'session': 'WEEKEND',
            'equities_active': False,
            'crypto_active': True,
            'allow_buy': True,
            'conviction_modifier': 1.0,
            'reason': 'Weekend — equities closed, crypto 24/7'
        }

    # Pre-market (before 9:30 ET)
    if time_decimal < 9.5:
        return {
            'session': 'PRE_MARKET',
            'equities_active': False,
            'crypto_active': True,
            'allow_buy': False,
            'conviction_modifier': 0.5,
            'reason': 'Pre-market — equities not yet open'
        }

    # Prime morning window (9:30-10:45 ET)
    if 9.5 <= time_decimal < 10.75:
        return {
            'session': 'PRIME_MORNING',
            'equities_active': True,
            'crypto_active': True,
            'allow_buy': True,
            'conviction_modifier': 1.0,
            'reason': 'Prime morning window — full signals active'
        }

    # Mid-day churn zone (10:45-15:00 ET)
    if 10.75 <= time_decimal < 15.0:
        return {
            'session': 'MIDDAY_CHURN',
            'equities_active': True,
            'crypto_active': True,
            'allow_buy': False,
            'conviction_modifier': 0.6,
            'reason': 'Mid-day churn zone — high volume delta, low price movement. No new BUY signals.'
        }

    # Prime closing window (15:00-15:30 ET)
    if 15.0 <= time_decimal < 15.5:
        return {
            'session': 'PRIME_CLOSE',
            'equities_active': True,
            'crypto_active': True,
            'allow_buy': True,
            'conviction_modifier': 1.0,
            'reason': 'Prime closing window — full signals active'
        }

    # Closing 30 min danger zone (15:30-16:00 ET)
    if 15.5 <= time_decimal < 16.0:
        return {
            'session': 'CLOSING_DANGER',
            'equities_active': True,
            'crypto_active': True,
            'allow_buy': False,
            'conviction_modifier': 0.0,
            'reason': 'Closing 30min — manipulation risk. No new signals.'
        }

    # After-hours (after 16:00 ET)
    return {
        'session': 'AFTER_HOURS',
        'equities_active': False,
        'crypto_active': True,
        'allow_buy': True,
        'conviction_modifier': 1.0,
        'reason': 'After-hours — equities closed, crypto 24/7'
    }
