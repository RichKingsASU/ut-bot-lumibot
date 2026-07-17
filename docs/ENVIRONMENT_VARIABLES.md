# Environment Variables Reference

This document catalogs the required and optional environment variables for the trading backend and frontend dashboard.

## 🔑 Backend Environment Variables (`.env`)

These variables configure broker access, database connectivity, notifications, and AI agents.

| Variable Name | Required | Role / Usage |
| :--- | :---: | :--- |
| `ALPACA_API_KEY` | **Yes** | Alpaca Brokerage Paper/Live API Key ID. |
| `ALPACA_API_SECRET` | **Yes** | Alpaca Brokerage Paper/Live API Secret Key. |
| `ALPACA_BASE_URL` | **Yes** | Alpaca API Base URL (e.g. `https://paper-api.alpaca.markets`). |
| `ALPACA_DATA_URL` | **Yes** | Alpaca Data feed URL (e.g. `https://data.alpaca.markets`). |
| `ALPACA_IS_PAPER` | **Yes** | `true` for paper trading, `false` for live execution. |
| `INGEST_SYMBOLS` | **Yes** | Comma-separated list of tickers to fetch (e.g. `SPY,QQQ,BTC/USD`). |
| `SUPABASE_URL` | **Yes** | URL of your production Supabase project. |
| `SUPABASE_SERVICE_ROLE_KEY` | **Yes** | Service role JWT bypass key for database writes. |
| `TELEGRAM_BOT_TOKEN` | No | API token of your Telegram notification bot. |
| `TELEGRAM_CHAT_ID` | No | Telegram channel or personal chat identifier. |
| `FINNHUB_API_KEY` | No | Finnhub API credential for financial news feeds. |
| `ANTHROPIC_API_KEY_AGENTS` | No | Anthropic API key for debate agent modeling. |
| `ANTHROPIC_API_KEY_SENTIMENT` | No | Anthropic API key for sentiment scorer. |
| `ANTHROPIC_API_KEY_HERMES` | No | Anthropic API key for Hermes agent. |
| `HUGGINGFACE_TOKEN` | No | Hugging Face token for local FinBERT scoring. |
| `TRADING_MODE` | **Yes** | Active execution mode: `PAPER` or `LIVE`. |

---

## 💻 Frontend Build Variables (`dashboard/.env`)

Vite requires variables to be prefixed with `VITE_` to expose them to the client browser.

| Variable Name | Required | Role / Usage |
| :--- | :---: | :--- |
| `VITE_SUPABASE_URL` | **Yes** | Production Supabase URL. |
| `VITE_SUPABASE_ANON_KEY` | **Yes** | Production Supabase anonymous public key. |
| `VITE_DEFAULT_SYMBOL` | No | Ticker default for details panels (default: `IWM`). |
| `VITE_DEFAULT_TIMEFRAME` | No | Standard bar interval (default: `15m`). |
| `VITE_REFRESH_INTERVAL` | No | Dashboard polling rate in ms (default: `15000`). |

---

## 🌐 Netlify Edge Variables

Configure these settings in the Netlify admin panel (`Build & deploy` > `Environment`):

| Variable Name | Value / Reference |
| :--- | :--- |
| `SUPABASE_URL` | Production Supabase URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Production Supabase Service Role Key |
| `ALPACA_API_KEY` | Alpaca Paper API Key ID |
| `ALPACA_API_SECRET` | Alpaca Paper API Secret Key |
| `ALPACA_BASE_URL` | Alpaca Base URL |
| `ADMIN_API_KEY` | Authorization key for Netlify function endpoints |
