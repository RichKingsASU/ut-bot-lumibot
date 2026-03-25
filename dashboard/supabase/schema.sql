-- ── Drop old partial schema if it exists ──────────────────
DROP TABLE IF EXISTS options_chain CASCADE;
DROP TABLE IF EXISTS options_chain_archive CASCADE;

-- ── OHLCV bars (already exists — verify columns match) ────
-- If ohlcv_bars already exists, just confirm these columns:
-- symbol, timeframe, ts, open, high, low, close, volume,
-- vwap, trade_count, feed, created_at
-- If it does NOT exist, create it:

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
) PARTITION BY RANGE (ts);

-- Note: Ensure pg_partman is enabled
-- SELECT partman.create_parent(
--   p_parent_table => 'public.ohlcv_bars',
--   p_control      => 'ts',
--   p_interval     => '1 month',
--   p_premake      => 3
-- );

CREATE INDEX IF NOT EXISTS idx_ohlcv_sym_tf_ts
  ON ohlcv_bars (symbol, timeframe, ts DESC);

-- ── Full options chain snapshot table ─────────────────────
CREATE TABLE options_chain (
  id                    BIGSERIAL,
  snapshot_ts           TIMESTAMPTZ   NOT NULL,

  -- Contract identity
  contract_symbol       TEXT          NOT NULL,
  underlying            TEXT          NOT NULL,
  expiration_date       DATE          NOT NULL,
  strike_price          NUMERIC(12,4) NOT NULL,
  option_type           CHAR(1)       NOT NULL,   -- 'C' or 'P'
  contract_style        TEXT,                     -- 'american'
  contract_size         SMALLINT,                 -- 100

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

  -- Greeks (all 5 — may be NULL for 0DTE)
  delta                 NUMERIC(10,6),
  gamma                 NUMERIC(10,6),
  theta                 NUMERIC(10,6),
  vega                  NUMERIC(10,6),
  rho                   NUMERIC(10,6),

  -- Open interest (from contract metadata, updated daily)
  open_interest         INTEGER,
  open_interest_date    DATE,

  -- Previous day close (from contract metadata)
  prev_close_price      NUMERIC(10,4),
  prev_close_date       DATE,

  -- Data quality flags
  has_greeks            BOOLEAN       NOT NULL DEFAULT FALSE,
  has_trade             BOOLEAN       NOT NULL DEFAULT FALSE,
  has_quote             BOOLEAN       NOT NULL DEFAULT FALSE,
  feed                  TEXT          NOT NULL DEFAULT 'opra',

  PRIMARY KEY (id, snapshot_ts)
) PARTITION BY RANGE (snapshot_ts);

-- SELECT partman.create_parent(
--   p_parent_table => 'public.options_chain',
--   p_control      => 'snapshot_ts',
--   p_interval     => '1 month',
--   p_premake      => 3
-- );

-- Indexes for common query patterns
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

-- ── Seed job tracking table ────────────────────────────────
CREATE TABLE IF NOT EXISTS seed_jobs (
  id            BIGSERIAL     PRIMARY KEY,
  job_type      TEXT          NOT NULL,  -- 'bars' | 'options_seed'
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

-- ── Useful views ───────────────────────────────────────────
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

-- ── RLS policies ───────────────────────────────────────────
ALTER TABLE options_chain   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ohlcv_bars      ENABLE ROW LEVEL SECURITY;
ALTER TABLE seed_jobs       ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON options_chain
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON ohlcv_bars
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON seed_jobs
  FOR ALL TO service_role USING (true);

-- ── pg_partman & pg_cron setup instructions ──────────────────
-- These should be run manually in the Supabase SQL editor:
/*
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Initialize partitions
SELECT partman.create_parent(
  p_parent_table => 'public.ohlcv_bars',
  p_control      => 'ts',
  p_interval     => '1 month',
  p_premake      => 3
);

SELECT partman.create_parent(
  p_parent_table => 'public.options_chain',
  p_control      => 'snapshot_ts',
  p_interval     => '1 month',
  p_premake      => 3
);

-- Schedule maintenance
SELECT cron.schedule(
  'partman-maintenance',
  '0 * * * *',
  $$SELECT partman.run_maintenance()$$
);

-- Daily open interest refresh at 6:30 AM EST (11:30 UTC)
SELECT cron.schedule(
  'refresh-open-interest',
  '30 11 * * 1-5',
  $$
  UPDATE options_chain oc
  SET open_interest      = c.oi,
      open_interest_date = c.oi_date,
      prev_close_price   = c.cp,
      prev_close_date    = c.cp_date
  FROM (
    SELECT contract_symbol,
           MAX(open_interest)      AS oi,
           MAX(open_interest_date) AS oi_date,
           MAX(prev_close_price)   AS cp,
           MAX(prev_close_date)    AS cp_date
    FROM options_chain
    WHERE snapshot_ts >= NOW() - INTERVAL '2 days'
    GROUP BY contract_symbol
  ) c
  WHERE oc.contract_symbol = c.contract_symbol
    AND oc.snapshot_ts >= CURRENT_DATE;
  $$
);
*/
