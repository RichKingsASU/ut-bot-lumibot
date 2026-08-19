from datetime import datetime, timedelta, timezone

import pytest

from src.trading.data_validity import DataStatus, EntryReadiness, ValidatedValue
from src.trading.decision_inputs import (
    aggregate_sentiment, format_sentiment, validate_agent_decision, validate_bars,
    validate_option_quote, validate_risk_value,
)

NOW = datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc)


def bar(age=0, **updates):
    value = {"open": 100, "high": 102, "low": 99, "close": 101,
             "timestamp": (NOW - timedelta(seconds=age)).isoformat(),
             "symbol": "SPY", "timeframe": "5Min"}
    value.update(updates); return value


@pytest.mark.parametrize("rows,status", [
    ([], DataStatus.NO_DATA),
    ([bar(700)], DataStatus.STALE),
    ([bar(close=-1)], DataStatus.MALFORMED),
    ([bar(high=98)], DataStatus.MALFORMED),
    ([{"close": 1}], DataStatus.MALFORMED),
])
def test_invalid_intraday_bars_are_explicit(rows, status):
    assert validate_bars(rows, source="ALPACA_5M", expected_symbol="SPY",
                         expected_timeframe="5Min", max_age_seconds=360, now=NOW).status is status


def test_valid_intraday_and_completed_daily_bars():
    assert validate_bars([bar(60)], source="ALPACA_5M", expected_symbol="SPY",
                         expected_timeframe="5Min", max_age_seconds=360, now=NOW).valid
    daily = bar(20 * 3600, timeframe="1Day")
    assert validate_bars([daily], source="ALPACA_DAILY_COMPLETED", expected_symbol="SPY",
                         expected_timeframe="1Day", max_age_seconds=36 * 3600, now=NOW).valid


@pytest.mark.parametrize("updates,status", [
    ({"bid": 0}, DataStatus.ZERO_BID), ({"ask": 0}, DataStatus.MALFORMED),
    ({"bid": 2, "ask": 1}, DataStatus.CROSSED_QUOTE),
    ({"timestamp": (NOW-timedelta(seconds=31)).isoformat()}, DataStatus.STALE_QUOTE),
    ({"timestamp": None}, DataStatus.MALFORMED),
    ({"bid": 1, "ask": 2}, DataStatus.INVALID_SPREAD),
])
def test_invalid_option_quotes_block(updates, status):
    quote = {"bid": 1, "ask": 1.1, "timestamp": NOW.isoformat(), "contract": "SPY-C"}
    quote.update(updates)
    result = validate_option_quote(quote, contract="SPY-C", now=NOW)
    assert result.status is status and not result.valid


def test_valid_option_quote():
    result = validate_option_quote({"bid": 1, "ask": 1.1, "timestamp": NOW.isoformat(),
                                    "contract": "SPY-C"}, contract="SPY-C", now=NOW)
    assert result.valid and result.value["mid"] == pytest.approx(1.05)


def test_sentiment_valid_zero_is_not_missing():
    articles = [{"score": 0.0, "timestamp": NOW.isoformat()} for _ in range(10)]
    result = aggregate_sentiment(articles, fetched_count=10, now=NOW)
    assert result.valid and result.value["avg_sentiment"] == 0.0
    assert "0.0000 (10 scored articles) [VALID]" in format_sentiment(result)


@pytest.mark.parametrize("kwargs,status", [
    ({"articles": [], "fetched_count": 0}, DataStatus.NO_DATA),
    ({"articles": [{"score": None, "timestamp": NOW.isoformat()}], "fetched_count": 10}, DataStatus.NO_DATA),
    ({"articles": [], "fetched_count": 0, "error": "TIMEOUT"}, DataStatus.ERROR),
    ({"articles": [], "fetched_count": 0, "disabled": True}, DataStatus.DISABLED),
    ({"articles": [{"score": .2, "timestamp": (NOW-timedelta(hours=2)).isoformat()}], "fetched_count": 1}, DataStatus.STALE),
])
def test_missing_failed_and_stale_sentiment_never_become_neutral(kwargs, status):
    result = aggregate_sentiment(now=NOW, **kwargs)
    assert result.status is status and result.value is None
    assert "0.0000 (0 articles)" not in format_sentiment(result)


def test_risk_valid_zero_differs_from_query_failure():
    pnl = validate_risk_value(0.0, source="BROKER_PNL", timestamp=NOW, now=NOW)
    failed = validate_risk_value(None, source="BROKER_PNL", timestamp=NOW, error="timeout", now=NOW)
    equity = validate_risk_value(100_000, source="BROKER_ACCOUNT", timestamp=NOW, positive=True, now=NOW)
    bad_equity = validate_risk_value(None, source="BROKER_ACCOUNT", timestamp=NOW, error="timeout", positive=True, now=NOW)
    assert pnl.valid and pnl.value == 0.0 and equity.valid
    assert failed.status is DataStatus.ERROR and failed.value is None
    assert bad_equity.status is DataStatus.ERROR and bad_equity.value is None


def test_entry_gate_fails_closed_but_does_not_gate_exit():
    stale = ValidatedValue(None, DataStatus.STALE, NOW, "ALPACA_5M", observed_at=NOW)
    missing = ValidatedValue(None, DataStatus.NO_DATA, NOW, "FINNHUB", observed_at=NOW)
    readiness = EntryReadiness.evaluate([("STALE_INTRADAY_BARS", stale), ("NO_SENTIMENT", missing)],
                                        lease_owned=True, broker_reconciled=True)
    assert not readiness.entry_allowed
    assert readiness.reason_codes == ("STALE_INTRADAY_BARS", "NO_SENTIMENT")
    emergency_exit_allowed = True  # entry readiness is intentionally never consulted by exit/kill APIs
    assert emergency_exit_allowed


def test_agent_timeout_is_not_valid_hold():
    assert validate_agent_decision("HOLD", required=True).valid
    failure = validate_agent_decision(None, required=True, error="timeout")
    assert failure.status is DataStatus.ERROR and failure.value is None


def test_false_green_cycle_is_degraded_and_entry_blocked():
    stale = validate_bars([bar(700)], source="ALPACA_5M", expected_symbol="SPY",
                          expected_timeframe="5Min", max_age_seconds=360, now=NOW)
    news = aggregate_sentiment([], fetched_count=0, now=NOW)
    readiness = EntryReadiness.evaluate([("STALE_INTRADAY_BARS", stale), ("NO_SENTIMENT", news)],
                                        lease_owned=True, broker_reconciled=True)
    health = {**stale.health("intraday_bar"), **news.health("sentiment"),
              "process_alive": True, "collector_alive": True,
              "entry_allowed": readiness.entry_allowed,
              "entry_block_reason": list(readiness.reason_codes)}
    assert health["process_alive"] and health["collector_alive"]
    assert health["intraday_bar_status"] == "STALE" and health["sentiment_status"] == "NO_DATA"
    assert not health["entry_allowed"]
