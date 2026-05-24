from adapters.json_logger import setup_logging
setup_logging()

import signal
import sys
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from strategies.adaptive_trend_mr_eth import AdaptiveTrendMR
from strategies import heartbeat
from config import ALPACA_CONFIG
import adapters.supabase_logger as db
import adapters.telegram_alerts as tg


def _shutdown_handler(signum, frame):
    print(f"\nReceived signal {signum}, shutting down...")
    from strategies.health_server import set_ready
    set_ready(False)  # Signal not ready
    heartbeat.stop()
    # Allow 1s for cleanup
    import time
    time.sleep(1)
    sys.exit(0)


from strategies.options_executor import sync_state_with_broker

from logger import bot_logger, ErrorCategory

# ETH/USD crypto market (24/7). main.py owns equities (SPY/QQQ/IWM).
SYMBOL = "ETH/USD"


def main():
    session_id = db.generate_session_id()
    bot_logger.info(f"Crypto Bot Session Started: {session_id}", category=ErrorCategory.INFRASTRUCTURE)

    if not db.check_connectivity():
        bot_logger.error("Supabase Connectivity Failed. Operational integrity at risk.", category=ErrorCategory.INFRASTRUCTURE)
    tg.check_connectivity()

    from config_validator import validate_production_env
    try:
        validate_production_env()
    except Exception as e:
        bot_logger.error(f"Environment Validation Failed: {e}", category=ErrorCategory.SECURITY)
        sys.exit(1)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    # Health server on port 8001 to avoid clashing with the equities bot (main.py on 8000)
    from strategies.health_server import start_health_server, set_ready
    start_health_server(8001)

    # ── [RELIABILITY] Sync state with broker before starting ─────────────
    try:
        sync_state_with_broker(SYMBOL)
    except Exception as e:
        bot_logger.warning(f"Initial Broker Sync Failed: {e}. Retrying during strategy loop.")

    set_ready(True)

    try:
        broker = Alpaca(ALPACA_CONFIG)
        strategy = AdaptiveTrendMR(broker=broker)
        symbol = f'{strategy.parameters.get("symbol", "ETH")}/{strategy.parameters.get("quote_symbol", "USD")}'

        db.log_session_start(symbol, metadata={
            "broker": "alpaca_paper" if ALPACA_CONFIG.get("PAPER") else "alpaca_live",
            "strategy": "AdaptiveTrendMR",
            "parameters": {k: str(v) for k, v in strategy.parameters.items()},
        })
        mode = "PAPER" if ALPACA_CONFIG.get("PAPER") else "LIVE"
        tg.send_alert(
            f"🚀 DisruptingAlpha CRYPTO BOT STARTED\n"
            f"Strategy: AdaptiveTrendMR\nMode: {mode}\nSymbol: {symbol}\nSession: {session_id}"
        )

        trader = Trader()
        trader.add_strategy(strategy)
        heartbeat.start()

        # NOTE: AlpacaStreamer is intentionally NOT started here — main.py owns
        # real-time equities streaming. This process only runs the crypto loop.

        bot_logger.info("Starting Lumibot Crypto Trader Loop...", category=ErrorCategory.INFRASTRUCTURE)
        trader.run_all()

    except Exception as e:
        bot_logger.error(f"Fatal crash in crypto trade loop: {e}", category=ErrorCategory.CRITICAL, exc_info=True)
        tg.send_error(f"Crypto bot crashed: {e}")
    finally:
        bot_logger.info("Initiating Graceful Shutdown...", category=ErrorCategory.INFRASTRUCTURE)
        heartbeat.stop()
        db.log_session_end()
        tg.send_alert("🛑 Crypto bot stopped — session ended")


if __name__ == "__main__":
    main()
