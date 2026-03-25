# 8-Screen Trading Dashboard Architecture

## Project Structure
- `src/components/dashboard/`: Core dashboard views
  - `Trade`: Order execution and management
  - `Options`: Options chain and Greek analysis
  - `Crypto`: Digital asset monitoring
  - `Backtest`: Lumibot strategy historical testing
  - `Portfolio`: Equity tracking and snapshotting
  - `Data`: SIP/OPRA data management
  - `Alerts`: Real-time signal management
  - `Settings`: User and strategy configuration

## Integration Rules
- **Alpaca**: Used for trading, market data (SIP), and options (OPRA).
- **Lumibot**: Primary strategy framework for backtesting and live execution.
- **Supabase**: Primary database for strategies, portfolio snapshots, and user settings.
- **Netlify**: Hosting and background execution (orchestrator).

## Database Schema
- `strategies`: JSONB parameters for Lumibot bots.
- `portfolio_snapshots`: Time-series equity tracking.
- `user_settings`: Global system configuration.

## Netlify Functions
- `sync-alpaca-history-background`: Runs every 5 minutes to fetch latest trades.
- `manage-strategy-orchestrator-background`: Manages the lifecycle of agentic trading strategies.
