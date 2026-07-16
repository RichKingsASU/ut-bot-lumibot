import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Make repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backtests.config import BacktestConfig
from backtests.data import _load_questdb, load_underlying


@pytest.fixture
def mock_config():
    return BacktestConfig(
        symbol="BTCUSD",
        timeframe="15m",
        start=date(2026, 5, 27),
        end=date(2026, 5, 27),
        use_questdb=True,
        questdb_url="http://localhost:9000"
    )


@patch("requests.get")
def test_load_questdb_success(mock_get, mock_config):
    # Set up mock JSON response matching QuestDB rest response format
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "query": "SELECT ...",
        "columns": [
            {"name": "timestamp", "type": "TIMESTAMP"},
            {"name": "open", "type": "DOUBLE"},
            {"name": "high", "type": "DOUBLE"},
            {"name": "low", "type": "DOUBLE"},
            {"name": "close", "type": "DOUBLE"},
            {"name": "volume", "type": "DOUBLE"}
        ],
        "dataset": [
            ["2026-05-27T13:30:00.000000Z", 70000.0, 70500.0, 69900.0, 70200.0, 1.5],
            ["2026-05-27T13:45:00.000000Z", 70200.0, 70300.0, 70100.0, 70150.0, 0.8]
        ]
    }
    mock_get.return_value = mock_resp

    df = _load_questdb(mock_config)

    assert df is not None
    assert len(df) == 2
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex)
    # Check conversion to tz America/New_York (UTC 13:30 is 9:30 ET)
    assert df.index[0].hour == 9
    assert df.index[0].minute == 30
    assert str(df.index[0].tz) == "America/New_York"
    assert df["close"].iloc[0] == 70200.0


@patch("requests.get")
def test_load_questdb_failure_status(mock_get, mock_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_get.return_value = mock_resp

    df = _load_questdb(mock_config)
    assert df is None


@patch("requests.get")
def test_load_questdb_empty_dataset(mock_get, mock_config):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "columns": [],
        "dataset": []
    }
    mock_get.return_value = mock_resp

    df = _load_questdb(mock_config)
    assert df is None


@patch("requests.get")
def test_load_underlying_with_questdb(mock_get, mock_config):
    # Test public loader integration
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "columns": [
            {"name": "timestamp", "type": "TIMESTAMP"},
            {"name": "open", "type": "DOUBLE"},
            {"name": "high", "type": "DOUBLE"},
            {"name": "low", "type": "DOUBLE"},
            {"name": "close", "type": "DOUBLE"},
            {"name": "volume", "type": "DOUBLE"}
        ],
        # Provide regular trading hours ticks so they are not filtered out by _filter_rth
        "dataset": [
            ["2026-05-27T13:30:00.000000Z", 70000.0, 70500.0, 69900.0, 70200.0, 1.5],
            ["2026-05-27T13:45:00.000000Z", 70200.0, 70300.0, 70100.0, 70150.0, 0.8]
        ]
    }
    mock_get.return_value = mock_resp

    sd = load_underlying(mock_config)
    resampled = sd.data
    source = sd.provenance.value
    assert "questdb" in source
    assert len(resampled) > 0
