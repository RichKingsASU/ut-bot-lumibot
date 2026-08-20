# Configuration Guide

The UT Bot uses .env for secrets and 
untime_config.json for UI-driven strategy parameters.

## Environment Variables

### Core Mode
- TRADING_MODE: Must be paper or live. Missing or invalid values will crash the bot.
- I_CONFIRM_LIVE_TRADING_EXPECTED_ACCOUNT: Required if live. Exact Alpaca account ID to prevent credential mistakes.

### Alpaca
- ALPACA_API_KEY: Key ID.
- ALPACA_API_SECRET: Secret Key.
- ALPACA_BASE_URL: Endpoint (e.g., https://paper-api.alpaca.markets).
- ALPACA_DATA_URL: Data endpoint.

### Telemetry / Auth
- SUPABASE_URL: Remote Postgres/telemetry host.
- SUPABASE_SERVICE_ROLE_KEY: Service role for bot writing logs.
- ADMIN_API_KEY: Key to authorize dashboard commands.

### Risk Management (Overrides UI)
- MAX_DAILY_LOSS: Hard limit on daily dollar loss (e.g., 500.0).
- MAX_POSITION_SIZE: Hard limit on concurrent contracts.
- MAX_TRADES_PER_DAY: Protects against runaway loops.
