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
    if not is_paper:
        logger.warning("🚨 LIVE TRADING ENABLED 🚨")
        if "paper-api" in ALPACA_BASE_URL:
            logger.error("FATAL: ALPACA_IS_PAPER is False but BASE_URL points to paper-api. Inconsistent config.")
            sys.exit(1)
    else:
        logger.info("Trading Mode: PAPER (Verified)")
        if "paper-api" not in ALPACA_BASE_URL:
            logger.warning("WARNING: ALPACA_IS_PAPER is True but BASE_URL points to live API. Fixing...")
            # This is handled in config.py but good to log here
            
    # 3. Risk Limit Validation
    if MAX_DAILY_LOSS <= 0:
        logger.error("FATAL: MAX_DAILY_LOSS must be a positive number. Current: %s", MAX_DAILY_LOSS)
        sys.exit(1)
        
    if not ADMIN_API_KEY or len(ADMIN_API_KEY) < 16:
        logger.warning("SECURITY WARNING: ADMIN_API_KEY is missing or weak. Dashboard access may be insecure.")

    logger.info("Environment validation successful.")
