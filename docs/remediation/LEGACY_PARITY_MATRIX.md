# Legacy Functional Parity Matrix

This is a preservation map, not a claim that a capability is production safe. “Partial” means source/tests exist but the audit found no production-like proof.

| Capability | Existing | Tested | Business Logic Located | Data Source | Refactor Target |
|---|---|---|---|---|---|
| Authentication | Yes | Partial UI | `dashboard/src/App.tsx`, `LoginPage.tsx`, Netlify auth helper | Supabase Auth | Django sessions/accounts |
| Dashboard | Yes | Component tests blocked | `dashboard/src/components/dashboard/` | Supabase, Alpaca, functions | Django templates + Bootstrap |
| Ingestion | Yes | Partial | `collectors/`, `run_*collector.py` | Alpaca, NATS, QuestDB | `markets` services + jobs |
| Market data | Yes | Partial | collectors, dashboard hooks/functions | Alpaca, QuestDB, Supabase | PostgreSQL market models/services |
| Trading | Yes | Partial | `main.py`, `strategies/`, `src/trading/` | Alpaca + local state | `trading` transactional service |
| Order entry | Yes | Partial | `strategies/options_executor.py`, `src/trading/executor.py` | Alpaca | Order model + broker adapter |
| Exits | Yes | Partial | UT strategy, executor, flatten function | Alpaca | reviewed transition service |
| Position management | Yes | Partial | executor, dashboard positions | Alpaca/Supabase | Position model + reconciliation |
| Reconciliation | Partial | Partial | `scripts/position_reconciliation.py`, startup sync | Alpaca/local/Supabase | `reconciliation` service/runs |
| Kill switch | Yes | Partial | orchestrator, watchdog, flatten function/scripts | Process + Alpaca | durable DB control + audited service |
| Human-in-the-loop | Partial | No proof | dashboard order/settings/emergency controls | Browser/functions | server-side confirmations |
| Observability | Yes | Partial | health server, JSON logger, heartbeats, Telegram | logs/Supabase | Django logging + health/audit |
| Administration | Partial | No proof | Settings UI, shared admin header | Supabase/functions | Django admin + explicit permissions |
| Role management | No adequate RBAC | No | generic authenticated/service roles | Supabase Auth/RLS | Django groups/permissions |
| Reporting | Yes | Partial | backtest reports, daily P&L, performance views | files/Supabase/Alpaca | read-only queries/templates |
| Historical data | Yes | Partial | seed scripts, backtests, historical UI data | Supabase/QuestDB/files | normalized PostgreSQL records |
| Configuration | Yes, fragmented | Partial | `config.py`, validator, `.env`, runtime settings UI | env/local/Supabase | typed Django settings + controlled DB config |

## Parity rule

Each target workflow requires a behavior-level regression test before the legacy path is retired. Existing defects and unproven behavior remain ledger items rather than being silently redefined.
