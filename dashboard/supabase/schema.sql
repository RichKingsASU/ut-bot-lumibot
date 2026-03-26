-- ══════════════════════════════════════════════════════════
-- Disrupting Alpha — Database Schema (no pg_partman required)
-- Run this in the Supabase SQL Editor
-- ══════════════════════════════════════════════════════════

-- ── Drop old partitioned tables if they exist ─────────────
DROP TABLE IF EXISTS options_chain CASCADE;
DROP TABLE IF EXISTS options_chain_archive CASCADE;

-- ── OHLCV bars ────────────────────────────────────────────
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

CREATE INDEX IF NOT EXISTS idx_ohlcv_sym_tf_ts
  ON ohlcv_bars (symbol, timeframe, ts DESC);

-- ── Full options chain snapshot table ─────────────────────
CREATE TABLE options_chain (
  id                    BIGSERIAL     PRIMARY KEY,
  snapshot_ts           TIMESTAMPTZ   NOT NULL,

  -- Contract identity
  contract_symbol       TEXT          NOT NULL,
  underlying            TEXT          NOT NULL,
  expiration_date       DATE          NOT NULL,
  strike_price          NUMERIC(12,4) NOT NULL,
  option_type           CHAR(1)       NOT NULL,   -- 'C' or 'P'
  contract_style        TEXT,
  contract_size         SMALLINT,

  -- Computed fields
  dte                   SMALLINT,
  moneyness             NUMERIC(10,6),
  intrinsic_value       NUMERIC(10,4),
  extrinsic_value       NUMERIC(10,4),
  underlying_price      NUMERIC(12,4),

  -- Latest trade
  last_trade_price      NUMERIC(10,4),
  last_trade_size       INTEGER,
  last_trade_ts         TIMESTAMPTZ,
  last_trade_exchange   TEXT,
  last_trade_condition  TEXT,

  -- Latest quote (NBBO from SIP)
  bid_price             NUMERIC(10,4),
  bid_size              INTEGER,
  bid_exchange          TEXT,
  ask_price             NUMERIC(10,4),
  ask_size              INTEGER,
  ask_exchange          TEXT,
  quote_ts              TIMESTAMPTZ,
  quote_condition       TEXT,

  -- Derived from quote
  mid_price             NUMERIC(10,4),
  bid_ask_spread        NUMERIC(10,4),
  bid_ask_spread_pct    NUMERIC(8,4),

  -- Implied volatility
  implied_volatility    NUMERIC(10,6),

  -- Greeks
  delta                 NUMERIC(10,6),
  gamma                 NUMERIC(10,6),
  theta                 NUMERIC(10,6),
  vega                  NUMERIC(10,6),
  rho                   NUMERIC(10,6),

  -- Open interest
  open_interest         INTEGER,
  open_interest_date    DATE,

  -- Previous day close
  prev_close_price      NUMERIC(10,4),
  prev_close_date       DATE,

  -- Data quality flags
  has_greeks            BOOLEAN       NOT NULL DEFAULT FALSE,
  has_trade             BOOLEAN       NOT NULL DEFAULT FALSE,
  has_quote             BOOLEAN       NOT NULL DEFAULT FALSE,
  feed                  TEXT          NOT NULL DEFAULT 'opra'
);

CREATE INDEX idx_options_underlying_ts
  ON options_chain (underlying, snapshot_ts DESC);

CREATE INDEX idx_options_contract_ts
  ON options_chain (contract_symbol, snapshot_ts DESC);

CREATE INDEX idx_options_expiry_strike
  ON options_chain (underlying, expiration_date, strike_price, option_type);

CREATE INDEX idx_options_dte
  ON options_chain (underlying, dte, snapshot_ts DESC);

CREATE INDEX idx_options_delta
  ON options_chain (underlying, delta, snapshot_ts DESC)
  WHERE delta IS NOT NULL;

-- ── Seed job tracking table ───────────────────────────────
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

-- ── Backtest results ──────────────────────────────────────
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

-- ── Bot status (heartbeat from local bot) ───────────────────
CREATE TABLE IF NOT EXISTS bot_status (
  id              INTEGER       PRIMARY KEY DEFAULT 1,
  status          TEXT          NOT NULL DEFAULT 'offline',
  last_heartbeat  TIMESTAMPTZ,
  session_id      TEXT,
  symbol          TEXT,
  mode            TEXT,
  uptime_seconds  INTEGER,
  last_signal     TEXT,
  last_signal_time TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ   DEFAULT NOW()
);

-- Seed the single row
INSERT INTO bot_status (id, status) VALUES (1, 'offline')
  ON CONFLICT DO NOTHING;

ALTER TABLE bot_status ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON bot_status
  FOR ALL TO service_role USING (true);

CREATE POLICY "anon_read" ON bot_status
  FOR SELECT TO anon USING (true);

-- ── Bot signals ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_signals (
  id            BIGSERIAL     PRIMARY KEY,
  symbol        TEXT          NOT NULL,
  ts            TIMESTAMPTZ   NOT NULL,
  signal        TEXT          NOT NULL,  -- 'buy' | 'sell'
  price         NUMERIC(12,4),
  trail_stop    NUMERIC(12,4),
  atr           NUMERIC(12,4),
  metadata      JSONB,
  created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bot_signals_sym_ts
  ON bot_signals (symbol, ts DESC);

-- ── Views ─────────────────────────────────────────────────

-- Bar inventory view (referenced by seed-status function)
CREATE OR REPLACE VIEW bar_inventory AS
SELECT
  symbol,
  timeframe,
  feed,
  COUNT(*)                              AS bar_count,
  MIN(ts)::DATE                         AS earliest,
  MAX(ts)::DATE                         AS latest,
  ROUND(COUNT(*) / 390.0, 1)           AS approx_trading_days,
  MAX(created_at)                       AS last_ingested
FROM ohlcv_bars
GROUP BY symbol, timeframe, feed
ORDER BY symbol, timeframe;

-- Data inventory view (referenced by supabase-query function)
CREATE OR REPLACE VIEW data_inventory AS
SELECT
  symbol,
  timeframe,
  feed,
  COUNT(*)                              AS bar_count,
  MIN(ts)::DATE                         AS earliest,
  MAX(ts)::DATE                         AS latest,
  MAX(created_at)                       AS last_ingested
FROM ohlcv_bars
GROUP BY symbol, timeframe, feed
ORDER BY symbol, timeframe;

-- Options inventory view (referenced by supabase-query function)
CREATE OR REPLACE VIEW options_inventory AS
SELECT
  underlying,
  COUNT(DISTINCT contract_symbol)       AS contracts,
  COUNT(DISTINCT expiration_date)       AS expirations,
  MIN(snapshot_ts)::DATE                AS earliest_snapshot,
  MAX(snapshot_ts)::DATE                AS latest_snapshot,
  COUNT(*)                              AS total_rows
FROM options_chain
GROUP BY underlying
ORDER BY underlying;

-- Options chain summary view
CREATE OR REPLACE VIEW options_chain_summary AS
SELECT
  underlying,
  snapshot_ts::DATE                     AS snap_date,
  COUNT(*)                              AS contracts,
  COUNT(*) FILTER (WHERE option_type='C') AS calls,
  COUNT(*) FILTER (WHERE option_type='P') AS puts,
  COUNT(*) FILTER (WHERE has_greeks)    AS with_greeks,
  COUNT(*) FILTER (WHERE dte = 0)       AS dte_0,
  MIN(expiration_date)                  AS nearest_expiry,
  MAX(expiration_date)                  AS furthest_expiry,
  ROUND(AVG(implied_volatility)::NUMERIC, 4) AS avg_iv,
  ROUND(AVG(CASE WHEN option_type='C' AND ABS(delta-0.5)<0.1
    THEN implied_volatility END)::NUMERIC, 4) AS atm_call_iv,
  MAX(snapshot_ts)                      AS last_snapshot
FROM options_chain
GROUP BY underlying, snapshot_ts::DATE
ORDER BY underlying, snap_date DESC;

-- ── RLS policies ──────────────────────────────────────────
ALTER TABLE ohlcv_bars      ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_chain    ENABLE ROW LEVEL SECURITY;
ALTER TABLE seed_jobs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_signals      ENABLE ROW LEVEL SECURITY;

-- Allow service_role full access (used by Netlify functions)
CREATE POLICY "service_role_all" ON ohlcv_bars
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON options_chain
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON seed_jobs
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON backtest_results
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON bot_signals
  FOR ALL TO service_role USING (true);

-- Allow anon read access for dashboard queries via supabase-query function
CREATE POLICY "anon_read" ON ohlcv_bars
  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON options_chain
  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON bot_signals
  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON backtest_results
  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON seed_jobs
  FOR SELECT TO anon USING (true);
