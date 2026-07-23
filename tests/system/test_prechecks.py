import os
import pytest
import httpx

@pytest.mark.system
def test_environment_variables_injected():
    """Verify that essential environment variables are populated, implying Doppler injection succeeded."""
    essential_vars = [
        "ALPACA_API_KEY",
        "ALPACA_API_SECRET",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY"
    ]
    missing = [var for var in essential_vars if not os.getenv(var)]
    assert not missing, f"Missing critical environment variables: {missing}. Doppler injection may have failed."

@pytest.mark.system
def test_paper_trading_safety():
    """Ensure that the system correctly defaults to paper trading environments for safety."""
    assert os.getenv("ALPACA_IS_PAPER") == "True", "System safety check failed: ALPACA_IS_PAPER must be True during testing!"
    assert "paper" in os.getenv("ALPACA_BASE_URL", "").lower(), "Alpaca Base URL is not pointing to the paper environment."

@pytest.mark.system
def test_alpaca_api_connectivity():
    """Verify connectivity to Alpaca Paper API (will be blocked if trying to hit live via conftest)."""
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    # Quick health check endpoint (if applicable) or simple root ping
    try:
        response = httpx.get(f"{base_url}/v2/clock", headers={
            "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", "test"),
            "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET", "test")
        }, timeout=5.0)
        
        # We don't fail on 401 because we might be using fake keys in CI, but we want to know we can reach the server
        assert response.status_code in [200, 401, 403], f"Unexpected Alpaca API response: {response.status_code}"
    except httpx.RequestError as e:
        pytest.fail(f"Could not connect to Alpaca API: {e}")

@pytest.mark.system
def test_supabase_connectivity():
    """Verify that the Supabase URL is reachable."""
    supabase_url = os.getenv("SUPABASE_URL", "http://localhost")
    try:
        # Just ping the root or health endpoint to ensure DNS and network connectivity
        response = httpx.get(f"{supabase_url}/rest/v1/", timeout=5.0)
        assert response.status_code in [200, 401, 404], f"Unexpected Supabase response: {response.status_code}"
    except httpx.RequestError as e:
        pytest.fail(f"Could not connect to Supabase: {e}")
