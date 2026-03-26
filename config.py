import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ── Runtime config (UI-saved overrides) ──────────────────────────────────────
_RUNTIME_CONFIG_PATH = Path(__file__).parent / "runtime_config.json"


def _load_runtime_config() -> dict:
    """Load runtime_config.json if it exists, else return empty dict."""
    if _RUNTIME_CONFIG_PATH.exists():
        try:
            return json.loads(_RUNTIME_CONFIG_PATH.read_text())
        except Exception:
            return {}
    return {}


_runtime = _load_runtime_config()


def _get(key: str, default: str) -> str:
    """Read from runtime config first, then .env, then default."""
    val = _runtime.get(key)
    if val is not None:
        return str(val)
    return os.getenv(key, default)


def reload():
    """Re-read runtime_config.json and update module-level config vars."""
    global _runtime
    global OPTION_EXPIRATION_MODE, OPTION_EXPIRATION_DAYS_OUT
    global OPTION_STRIKE_MODE, OPTION_STRIKE_STEP, OPTION_MAX_DTE_FALLBACK

    _runtime = _load_runtime_config()
    OPTION_EXPIRATION_MODE = _get("OPTION_EXPIRATION_MODE", "0DTE")
    OPTION_EXPIRATION_DAYS_OUT = int(_get("OPTION_EXPIRATION_DAYS_OUT", "0"))
    OPTION_STRIKE_MODE = _get("OPTION_STRIKE_MODE", "ATM")
    OPTION_STRIKE_STEP = float(_get("OPTION_STRIKE_STEP", "1.0"))
    OPTION_MAX_DTE_FALLBACK = int(_get("OPTION_MAX_DTE_FALLBACK", "7"))


# ── Alpaca Configuration (for Lumibot broker) ───────────────────────────────
ALPACA_CONFIG = {
    "API_KEY": os.getenv("ALPACA_API_KEY"),
    "API_SECRET": os.getenv("ALPACA_API_SECRET"),
    "PAPER": os.getenv("ALPACA_IS_PAPER", "true").lower() == "true",
}

# Alpaca REST API (for direct options trading)
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
ALPACA_DATA_URL = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

# Supabase (optional — for trade logging)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ── Options contract configuration ──────────────────────────────────────────
OPTION_EXPIRATION_MODE = _get("OPTION_EXPIRATION_MODE", "0DTE")
OPTION_EXPIRATION_DAYS_OUT = int(_get("OPTION_EXPIRATION_DAYS_OUT", "0"))
OPTION_STRIKE_MODE = _get("OPTION_STRIKE_MODE", "ATM")
OPTION_STRIKE_STEP = float(_get("OPTION_STRIKE_STEP", "1.0"))
OPTION_MAX_DTE_FALLBACK = int(_get("OPTION_MAX_DTE_FALLBACK", "7"))
