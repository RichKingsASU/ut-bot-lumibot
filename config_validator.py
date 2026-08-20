import os
import sys
import logging
from config import ALPACA_CONFIG, ALPACA_BASE_URL, ADMIN_API_KEY, MAX_DAILY_LOSS

logger = logging.getLogger("config_validator")

def validate_production_env():
    """
    Strict validation for production readiness.
    Fails closed (sys.exit) if critical variables are missing or unsafe.
    """
    logger.info("Starting production environment validation...")

    from config import TRADING_MODE, I_CONFIRM_LIVE_TRADING_EXPECTED_ACCOUNT
    is_paper = ALPACA_CONFIG.get("PAPER", True)

    # 1. Critical Key Presence
    critical_vars = [
        "ALPACA_API_KEY",
        "ALPACA_API_SECRET",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "ADMIN_API_KEY"
    ]

    missing = [v for v in critical_vars if not os.getenv(v)]
    if missing:
        logger.error("FATAL: Missing critical environment variables: %s", ", ".join(missing))
        sys.exit(1)

    # 2. Paper/Live Isolation Verification

    if not TRADING_MODE in ["paper", "live"]:
        logger.error("FATAL: TRADING_MODE must be explicitly set to \"paper\" or \"live\".")
        sys.exit(1)

    if not is_paper:
        logger.warning("?? LIVE TRADING ENABLED ??")
        if "paper-api" in ALPACA_BASE_URL:
            logger.error("FATAL: TRADING_MODE is live but BASE_URL points to paper-api. Inconsistent config.")
            sys.exit(1)

        if not I_CONFIRM_LIVE_TRADING_EXPECTED_ACCOUNT:
            logger.error("FATAL: Live trading requires I_CONFIRM_LIVE_TRADING_EXPECTED_ACCOUNT to be set to your expected Alpaca account ID.")
            sys.exit(1)

    else:
        logger.info("Trading Mode: PAPER (Verified)")
        if "paper-api" not in ALPACA_BASE_URL:
            paper_endpoint = "https://paper-api.alpaca.markets"
            logger.warning(
                "ALPACA_IS_PAPER is True but ALPACA_BASE_URL=%s points to the live API. "
                "Overriding ALPACA_BASE_URL to the paper endpoint (%s) so no live "
                "orders can be placed while in paper mode.",
                ALPACA_BASE_URL, paper_endpoint,
            )
            # Actually correct the process environment so every downstream
            # os.getenv("ALPACA_BASE_URL") reader (run_agents, kelly_sizer,
            # macro_filter, watchdogs, …) resolves to the safe paper endpoint.
            os.environ["ALPACA_BASE_URL"] = paper_endpoint

    # 3. Risk Limit Validation
    if MAX_DAILY_LOSS <= 0:
        logger.error("FATAL: MAX_DAILY_LOSS must be a positive number. Current: %s", MAX_DAILY_LOSS)
        sys.exit(1)

    if not ADMIN_API_KEY or len(ADMIN_API_KEY) < 16:
        logger.warning("SECURITY WARNING: ADMIN_API_KEY is missing or weak. Dashboard access may be insecure.")

    logger.info("Environment validation successful.")
