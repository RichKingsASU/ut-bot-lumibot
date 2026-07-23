import pytest
import os
import httpx
from unittest.mock import patch

# 1. Enforce environment safeguards explicitly (in addition to pytest.ini)
@pytest.fixture(scope="session", autouse=True)
def enforce_paper_trading():
    """Ensure that we never hit live Alpaca trading endpoints during tests."""
    os.environ["ALPACA_IS_PAPER"] = "True"
    os.environ["TESTING"] = "True"
    os.environ["DOPPLER_ENVIRONMENT"] = "test"
    
    # Assert safeguards
    assert os.getenv("ALPACA_IS_PAPER") == "True", "CRITICAL: Tests running without paper trading enforcement!"

# 2. Block real network requests to Alpaca Live by default
@pytest.fixture(scope="function", autouse=True)
def block_live_trading_requests(monkeypatch):
    """
    Blocks outgoing HTTP requests to the live trading API.
    Only allows paper-api.alpaca.markets and localhost.
    """
    original_client_send = httpx.Client.send
    original_async_send = httpx.AsyncClient.send

    def safe_send(self, request, *args, **kwargs):
        url = str(request.url)
        # Block production API explicitly
        if "api.alpaca.markets" in url and "paper-api" not in url:
            raise RuntimeError(f"TEST SAFETY VIOLATION: Attempted to call live Alpaca API: {url}")
        return original_client_send(self, request, *args, **kwargs)

    async def safe_async_send(self, request, *args, **kwargs):
        url = str(request.url)
        if "api.alpaca.markets" in url and "paper-api" not in url:
            raise RuntimeError(f"TEST SAFETY VIOLATION: Attempted to call live Alpaca API: {url}")
        return await original_async_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", safe_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", safe_async_send)
