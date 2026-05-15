# 🤖 UT Bot — Algorithmic Trading Bot (Lumibot + Alpaca)

## Overview
A complete algorithmic trading bot implementing the **UT Bot (Ultimate Trailing Stop)** strategy. Built on the **Lumibot** framework and designed to connect seamlessly with **Alpaca Markets** for both paper and live trading.

## Features
- **UT Bot Strategy**: Dynamic ATR-based trailing stop for optimized entry and exit signals.
- **Alpaca Integration**: Robust support for Alpaca's REST API.
- **Automated Execution**: Handles order submission, tracking, and position management.
- **Security First**: Configuration via environment variables, ensuring no secrets are committed.
- **CI/CD Ready**: Includes GitHub Actions for syntax validation and security scanning.

## Project Structure
```text
project/
├── .env                  # local secrets (ignored by git)
├── .env.example          # template for secrets
├── .gitignore            # git ignore patterns
├── requirements.txt      # python dependencies
├── config.py             # credential loader
├── main.py               # entry point to run the bot
├── LICENSE               # MIT License
└── strategies/
    └── ut_bot.py         # UT Bot strategy implementation
```

## Quick Start
1. **Clone the repository**:
   ```bash
   git clone https://github.com/[your-username]/ut-bot-lumibot.git
   cd ut-bot-lumibot
   ```
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure your credentials**:
   Copy `.env.example` to `.env` and fill in your Alpaca API Key and Secret.
   ```bash
   cp .env.example .env
   ```
5. **Run the bot**:
   ```bash
   python main.py
   ```

## Configuration
The bot uses the following environment variables in `.env`:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ALPACA_API_KEY` | Your Alpaca Paper/Live API Key | Yes | - |
| `ALPACA_API_SECRET` | Your Alpaca Paper/Live API Secret | Yes | - |
| `ALPACA_IS_PAPER` | Whether to use Paper trading | No | `true` |

## UT Bot Strategy
The strategy uses an **ATR Trailing Stop** to generate signals:
- **ATR Period**: Lookback period for Average True Range (default: 1).
- **Sensitivity**: Multiplier for the ATR to determine stop distance (default: 1.0).
- **Signals**: 
  - **Buy**: When price crosses above the trailing stop.
  - **Sell**: When price crosses below the trailing stop.

## Data Seeding & Collector (Alpaca SIP + OPRA)
The project now includes a comprehensive data collection layer for historical and real-time data:

- **SIP Bar Seeding**: Backfills 2 years of historical SIP bars (100% volume) for IWM, SPY, and QQQ.
- **Options Chain Snapshots**: Captures full options chain snapshots ogni 5 minuti with all greeks (delta, gamma, theta, vega, rho) and Implied Volatility (IV).
- **Monitoring Dashboard**: A dedicated "Data" tab in the dashboard to track ingestion status and trigger manual backfills.

### Setup Ingestion
1. **SQL Schema**: Run `dashboard/supabase/schema.sql` in your Supabase SQL editor.
2. **Scheduled Functions**:
   - `ingest-bars`: Every 1 min during market hours.
   - `ingest-options-chain`: Every 5 mins during market hours.

## 🚨 Emergency Procedures (OAT Hardened)

### Manual Kill Switch
If the system enters an unstable state or significant slippage occurs:
1. **Primary Method**: Use the Alpaca Dashboard to "Cancel All Orders" and "Liquidate All Positions".
2. **Bot Shutdown**: 
   - Local: Press `CTRL+C` twice in the terminal running `main.py`.
   - Docker: `docker-compose down`.
   - PM2: `pm2 stop all`.

### Recovery Protocols (SOP-002)
- **Supabase Disconnect**: The bot will continue to trade using its last known trailing stop but will stop reporting to the dashboard. **Manual monitoring of Alpaca is required.**
- **Broker API Error**: The bot will log a `CRITICAL` error and halt all entry signals. It will attempt to manage existing exits via local ATR calculation.

## Disclaimer
This software is for educational purposes only. Do not use it for live trading without thorough testing. Algorithmic trading involves significant risk. **Past performance is not indicative of future results.**

## License
[MIT](LICENSE)
