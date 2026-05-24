-- ════════════════════════════════════════════════════════════════════════════
-- DISRUPTING ALPHA — CONSOLIDATED CLOUD SCHEMA SNAPSHOT (DOCUMENTATION ONLY)
-- ════════════════════════════════════════════════════════════════════════════
-- Project: wnigkahkamoizjpmpuxs.supabase.co
-- Generated: 2026-05-23 by codebase audit.
--
-- ⚠️  DOCUMENTATION ONLY — DO NOT RUN THIS AS A MIGRATION.
--     This records the ACTUAL current state of the cloud database, observed via
--     the live PostgREST OpenAPI spec and cross-referenced with the SQL files
--     under dashboard/supabase/migrations/ and dashboard/supabase/schema.sql.
--
-- NOTE: dashboard/supabase/schema.sql already exists and is the canonical,
--     executable seed script (referenced by README) for the ad-hoc data tables.
--     This file is a READ-ONLY inventory and intentionally does NOT replace it.
--
-- Provenance legend:
--   [MIGRATION]  — defined by a file in dashboard/supabase/migrations/
--   [SCHEMA.SQL] — defined by the canonical dashboard/supabase/schema.sql
--   [VIEW]       — read-only view / aggregate
--   [PENDING]    — defined in migrations/20260523000000_missing_tables.sql but
--                  NOT yet applied to cloud (exec_sql RPC unavailable)
-- ════════════════════════════════════════════════════════════════════════════


-- ════════════════════════════════════════════════════════════════════════════
-- LIVE BUSINESS / TRADING TABLES
-- ════════════════════════════════════════════════════════════════════════════

-- [MIGRATION 001 + 20260514010000] bot_status — heartbeat + remote C2 (1 row)
CREATE TABLE IF NOT EXISTS bot_status (
  id               INTEGER       PRIMARY KEY DEFAULT 1,
  status           TEXT          NOT NULL DEFAULT 'offline',
  last_heartbeat   TIMESTAMPTZ,
  session_id       TEXT,
  symbol           TEXT,
  mode             TEXT,
  uptime_seconds   INTEGER,
  last_signal      TEXT,
  last_signal_time TIMESTAMPTZ,
  updated_at       TIMESTAMPTZ   DEFAULT NOW(),
  target_status    TEXT          DEFAULT 'running'   -- C2: running|shutdown|restart
);

-- [MIGRATION 20260326] bar_log — 1m bars from the strategy loop (~267 rows)
CREATE TABLE IF NOT EXISTS bar_log (
  id          BIGSERIAL     PRIMARY KEY,
  session_id  TEXT          NOT NULL,
  symbol      TEXT          NOT NULL,
  bar_time    TIMESTAMPTZ   NOT NULL,
  open        NUMERIC(12,4),
  high        NUMERIC(12,4),
  low         NUMERIC(12,4),
  close       NUMERIC(12,4),
  volume      BIGINT,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- [MIGRATION 20260326] signal_log — every UT Bot signal (0 rows)
CREATE TABLE IF NOT EXISTS signal_log (
  id           BIGSERIAL     PRIMARY KEY,
  session_id   TEXT          NOT NULL,
  symbol       TEXT          NOT NULL,
  bar_time     TIMESTAMPTZ   NOT NULL,
  timeframe    TEXT          NOT NULL DEFAULT '1D',
  signal_type  TEXT          NOT NULL,
  close_price  NUMERIC(12,4),
  trail_stop   NUMERIC(12,4),
  atr          NUMERIC(12,4),
  rsi          NUMERIC(8,2),
  buy_sig      BOOLEAN,
  sell_sig     BOOLEAN,
  created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- [MIGRATION 20260326] paper_trades — entry/exit rows (0 rows)
CREATE TABLE IF NOT EXISTS paper_trades (
  id                     BIGSERIAL     PRIMARY KEY,
  session_id             TEXT          NOT NULL,
  symbol                 TEXT          NOT NULL,
  contract_symbol        TEXT,
  direction              TEXT,
  option_type            TEXT,
  strike                 NUMERIC(12,4),
  expiration             TEXT,
  qty                    INTEGER,
  side                   TEXT          NOT NULL,
  entry_price            NUMERIC(12,4),
  exit_price             NUMERIC(12,4),
  entry_underlying_price NUMERIC(12,4),
  exit_underlying_price  NUMERIC(12,4),
  trade_pnl              NUMERIC(14,2),
  cumulative_pnl         NUMERIC(14,2),
  exit_reason            TEXT,
  entry_rsi              NUMERIC(8,2),
  created_at             TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- [MIGRATION 20260326] sessions — bot session lifecycle (~15 rows)
CREATE TABLE IF NOT EXISTS sessions (
  id           BIGSERIAL     PRIMARY KEY,
  session_id   TEXT          UNIQUE NOT NULL,
  symbol       TEXT          NOT NULL,
  started_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  ended_at     TIMESTAMPTZ,
  status       TEXT          NOT NULL DEFAULT 'running',
  trades_count INTEGER       DEFAULT 0,
  total_pnl    NUMERIC(14,2) DEFAULT 0,
  metadata     JSONB
);

-- [MIGRATION 20260513] system_alerts — operator notifications (0 rows)
CREATE TABLE IF NOT EXISTS system_alerts (
  id          BIGSERIAL     PRIMARY KEY,
  session_id  TEXT          NOT NULL,
  ts          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  level       TEXT          NOT NULL,
  category    TEXT          NOT NULL,
  message     TEXT          NOT NULL,
  metadata    JSONB         DEFAULT '{}',
  is_resolved BOOLEAN       DEFAULT FALSE,
  resolved_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- [MIGRATION 20260513] system_audit — audit trail (~26 rows)
CREATE TABLE IF NOT EXISTS system_audit (
  id          BIGSERIAL     PRIMARY KEY,
  session_id  TEXT          NOT NULL,
  ts          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  action      TEXT          NOT NULL,
  status      TEXT          NOT NULL,
  details     TEXT,
  metadata    JSONB         DEFAULT '{}',
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- [SCHEMA.SQL] trade_log — broker order/fill ledger (0 rows)
-- Written by strategies/options_executor.py (log_trade_async).
CREATE TABLE IF NOT EXISTS trade_log (
  id                 BIGINT        PRIMARY KEY,   -- BIGSERIAL in practice
  ts                 TIMESTAMPTZ,
  alpaca_order_id    TEXT,
  symbol             TEXT,
  side               TEXT,
  qty                NUMERIC,
  order_type         TEXT,
  limit_price        NUMERIC,
  fill_price         NUMERIC,
  fill_qty           NUMERIC,
  status             TEXT,
  submitted_at       TIMESTAMPTZ,
  filled_at          TIMESTAMPTZ,
  unrealized_pnl     NUMERIC,
  realized_pnl       NUMERIC,
  portfolio_value    NUMERIC,
  trail_stop_at_fill NUMERIC,
  signal_id          BIGINT
);

-- [SCHEMA.SQL] bot_signals — ⚠️ BASE TABLE (NOT a view) (0 rows)
-- ⚠️ CONFLICT: migrations/20260523000000_missing_tables.sql tries to
--    `CREATE OR REPLACE VIEW bot_signals` over signal_log with DIFFERENT
--    columns. That statement will FAIL against cloud because bot_signals
--    already exists here as a base table. See "PENDING" note at bottom.
CREATE TABLE IF NOT EXISTS bot_signals (
  id          BIGSERIAL     PRIMARY KEY,
  symbol      TEXT          NOT NULL,
  ts          TIMESTAMPTZ   NOT NULL,
  signal      TEXT          NOT NULL,   -- 'buy' | 'sell'
  price       NUMERIC(12,4),
  trail_stop  NUMERIC(12,4),
  atr         NUMERIC(12,4),
  metadata    JSONB,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);


-- ════════════════════════════════════════════════════════════════════════════
-- LIVE MARKET-DATA / OPS TABLES (from dashboard/supabase/schema.sql)
-- ════════════════════════════════════════════════════════════════════════════

-- [SCHEMA.SQL] ohlcv_bars — real-time + seeded bars (~1.6M rows)
CREATE TABLE IF NOT EXISTS ohlcv_bars (
  symbol       TEXT          NOT NULL,
  timeframe    TEXT          NOT NULL,
  ts           TIMESTAMPTZ   NOT NULL,
  open         NUMERIC(12,4),
  high         NUMERIC(12,4),
  low          NUMERIC(12,4),
  close        NUMERIC(12,4),
  volume       BIGINT,
  vwap         NUMERIC(12,4),
  trade_count  INTEGER,
  feed         TEXT          NOT NULL DEFAULT 'sip',
  created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  PRIMARY KEY (symbol, timeframe, ts)
);

-- [SCHEMA.SQL] options_chain — OPRA chain snapshots w/ greeks (0 rows)
-- (43 columns — see dashboard/supabase/schema.sql for the full definition)

-- [SCHEMA.SQL] backtest_results — written by run-backtest Netlify fn (0 rows)
CREATE TABLE IF NOT EXISTS backtest_results (
  id                BIGSERIAL     PRIMARY KEY,
  strategy          TEXT          NOT NULL,
  symbol            TEXT          NOT NULL,
  timeframe         TEXT,
  data_source       TEXT,
  date_start        DATE,
  date_end          DATE,
  atr_period        INTEGER,
  sensitivity       NUMERIC(6,2),
  initial_capital   NUMERIC(14,2),
  final_value       NUMERIC(14,2),
  total_return_pct  NUMERIC(10,4),
  max_drawdown_pct  NUMERIC(10,4),
  sharpe_ratio      NUMERIC(10,4),
  total_trades      INTEGER,
  winning_trades    INTEGER,
  losing_trades     INTEGER,
  win_rate_pct      NUMERIC(8,4),
  avg_win           NUMERIC(14,2),
  avg_loss          NUMERIC(14,2),
  profit_factor     NUMERIC(10,4),
  params            JSONB,
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- [SCHEMA.SQL] seed_jobs — ingestion/seed job tracking
CREATE TABLE IF NOT EXISTS seed_jobs (
  id            BIGSERIAL     PRIMARY KEY,
  job_type      TEXT          NOT NULL,
  symbol        TEXT          NOT NULL,
  timeframe     TEXT,
  started_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  completed_at  TIMESTAMPTZ,
  status        TEXT          NOT NULL DEFAULT 'running',
  rows_written  INTEGER       DEFAULT 0,
  date_from     DATE,
  date_to       DATE,
  error_msg     TEXT,
  metadata      JSONB
);

-- [AD-HOC] user_settings — dashboard key/value config (2 rows)
-- ⚠️ Live shape is (id, key, value, updated_at) — DIFFERS from the
--    migrations_bak definition (id, user_id, settings, updated_at).
CREATE TABLE IF NOT EXISTS user_settings (
  id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  key        TEXT,
  value      JSONB,
  updated_at TIMESTAMPTZ
);

-- [AD-HOC] risk_config — dashboard risk rules (read by useRiskConfig hook)
CREATE TABLE IF NOT EXISTS risk_config (
  id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  mode       TEXT,
  rules      JSONB,
  updated_at TIMESTAMPTZ
);


-- ════════════════════════════════════════════════════════════════════════════
-- VIEWS (read-only, from dashboard/supabase/schema.sql)
-- ════════════════════════════════════════════════════════════════════════════
-- [VIEW] bar_inventory         — per (symbol,timeframe,feed) bar coverage
-- [VIEW] data_inventory        — bar coverage (dashboard Data tab)
-- [VIEW] options_inventory     — per-underlying option snapshot coverage
-- [VIEW] options_chain_summary — per (underlying, snap_date) chain stats + avg IV


-- ════════════════════════════════════════════════════════════════════════════
-- [PENDING] Not yet in cloud — from migrations/20260523000000_missing_tables.sql
-- ════════════════════════════════════════════════════════════════════════════
--   strategies          — StrategyLab persistence       (currently 404 in cloud)
--   portfolio_snapshots — Portfolio equity curve          (currently 404 in cloud)
--   bot_signals (VIEW)  — ⚠️ WILL FAIL: a base table named bot_signals already
--                         exists in cloud. Before applying that migration,
--                         either (a) drop the bot_signals line, or (b) DROP the
--                         existing bot_signals table first, or (c) rename the view.
