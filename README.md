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

## Disclaimer
This software is for educational purposes only. Do not use it for live trading without thorough testing. Algorithmic trading involves significant risk. **Past performance is not indicative of future results.**

## License
[MIT](LICENSE)
