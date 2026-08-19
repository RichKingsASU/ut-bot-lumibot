from unittest.mock import Mock, patch

from src.trading.data_validity import DataStatus
from src.trading.market_gap import check_gap


def response(payload):
    result = Mock(); result.json.return_value = payload; result.raise_for_status.return_value = None
    return result


@patch("src.trading.market_gap.requests.get")
def test_gap_uses_data_endpoint_and_returns_real_value(get):
    get.return_value = response({"bars": [{"c": 100, "o": 99, "t": "2026-08-18T20:00:00Z"},
                                                {"c": 102, "o": 101, "t": "2026-08-19T13:30:00Z"}]})
    result = check_gap("SPY")
    assert result.valid and result.value == .01
    assert get.call_args.args[0].startswith("https://data.alpaca.markets/")


@patch("src.trading.market_gap.requests.get")
def test_http_200_empty_bars_is_no_data_not_zero(get):
    get.return_value = response({"bars": []})
    result = check_gap("SPY")
    assert result.status is DataStatus.NO_DATA and result.value is None
