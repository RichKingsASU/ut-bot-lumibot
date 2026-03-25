-- Step 1b — Enable required extensions
CREATE SCHEMA IF NOT EXISTS partman;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Step 2a — OHLCV Bars Table (partitioned by month)
CREATE TABLE ohlcv_bars (
  symbol      TEXT        NOT NULL,
  timeframe   TEXT        NOT NULL,
  ts          TIMESTAMPTZ NOT NULL,
  open        NUMERIC(12,4),
  high        NUMERIC(12,4),
  low         NUMERIC(12,4),
  close       NUMERIC(12,4),
  volume      BIGINT,
  vwap        NUMERIC(12,4),
  trade_count INTEGER,
  feed        TEXT        NOT NULL DEFAULT 'iex',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (symbol, timeframe, ts)
) PARTITION BY RANGE (ts);

SELECT partman.create_parent(
  p_parent_table  => 'public.ohlcv_bars',
  p_control       => 'ts',
  p_interval      => '1 month',
  p_premake       => 3
);

CREATE INDEX idx_ohlcv_symbol_tf_ts
  ON ohlcv_bars (symbol, timeframe, ts DESC);

CREATE INDEX idx_ohlcv_feed
  ON ohlcv_bars (feed);

-- Step 2b — Options Chain Snapshots Table (partitioned by month)
CREATE TABLE options_chain (
  id              BIGSERIAL,
  ts              TIMESTAMPTZ NOT NULL,
  underlying      TEXT        NOT NULL,
  symbol          TEXT        NOT NULL,
  expiration      DATE        NOT NULL,
  strike          NUMERIC(10,2),
  option_type     CHAR(1),
  dte             SMALLINT,
  bid             NUMERIC(10,4),
  ask             NUMERIC(10,4),
  mid             NUMERIC(10,4),
  last            NUMERIC(10,4),
  volume          INTEGER,
  open_interest   INTEGER,
  iv              NUMERIC(8,6),
  delta           NUMERIC(8,6),
  gamma           NUMERIC(8,6),
  theta           NUMERIC(8,6),
  vega            NUMERIC(8,6),
  rho             NUMERIC(8,6),
  underlying_price NUMERIC(12,4),
  feed            TEXT        NOT NULL DEFAULT 'indicative',
  PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

SELECT partman.create_parent(
  p_parent_table  => 'public.options_chain',
  p_control       => 'ts',
  p_interval      => '1 month',
  p_premake       => 3
);

CREATE INDEX idx_options_underlying_ts
  ON options_chain (underlying, ts DESC);

CREATE INDEX idx_options_symbol_ts
  ON options_chain (symbol, ts DESC);

CREATE INDEX idx_options_expiration
  ON options_chain (underlying, expiration, strike, option_type);

-- Step 2c — Bot Signals Table
CREATE TABLE bot_signals (
  id          BIGSERIAL   PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  symbol      TEXT        NOT NULL,
  timeframe   TEXT        NOT NULL,
  signal      SMALLINT    NOT NULL,
  signal_text TEXT        GENERATED ALWAYS AS (
                CASE signal
                  WHEN  1 THEN 'BUY'
                  WHEN -1 THEN 'SELL'
                  ELSE 'HOLD'
                END
              ) STORED,
  price       NUMERIC(12,4),
  trail_stop  NUMERIC(12,4),
  atr         NUMERIC(10,6),
  atr_period  SMALLINT,
  sensitivity NUMERIC(4,2),
  portfolio_value NUMERIC(16,4),
  cash        NUMERIC(16,4)
);

CREATE INDEX idx_signals_symbol_ts
  ON bot_signals (symbol, ts DESC);

-- Step 2d — Trade Log Table
CREATE TABLE trade_log (
  id              BIGSERIAL   PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  alpaca_order_id TEXT        UNIQUE,
  symbol          TEXT        NOT NULL,
  side            TEXT        NOT NULL,
  qty             NUMERIC(12,4),
  order_type      TEXT,
  limit_price     NUMERIC(12,4),
  fill_price      NUMERIC(12,4),
  fill_qty        NUMERIC(12,4),
  status          TEXT,
  submitted_at    TIMESTAMPTZ,
  filled_at       TIMESTAMPTZ,
  unrealized_pnl  NUMERIC(16,4),
  realized_pnl    NUMERIC(16,4),
  portfolio_value NUMERIC(16,4),
  trail_stop_at_fill NUMERIC(12,4),
  signal_id       BIGINT REFERENCES bot_signals(id)
);

-- Step 2e — Backtest Results Table
CREATE TABLE backtest_results (
  id              BIGSERIAL   PRIMARY KEY,
  run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  strategy        TEXT        NOT NULL,
  symbol          TEXT        NOT NULL,
  timeframe       TEXT        NOT NULL,
  data_source     TEXT        NOT NULL,
  date_start      DATE        NOT NULL,
  date_end        DATE        NOT NULL,
  atr_period      SMALLINT,
  sensitivity     NUMERIC(4,2),
  initial_capital NUMERIC(16,4),
  final_value     NUMERIC(16,4),
  total_return_pct NUMERIC(10,4),
  max_drawdown_pct NUMERIC(10,4),
  sharpe_ratio    NUMERIC(8,4),
  total_trades    INTEGER,
  winning_trades  INTEGER,
  losing_trades   INTEGER,
  win_rate_pct    NUMERIC(8,4),
  avg_win         NUMERIC(12,4),
  avg_loss        NUMERIC(12,4),
  profit_factor   NUMERIC(8,4),
  notes           TEXT,
  params          JSONB
);

-- Step 2f — Data Inventory View (see what's stored)
CREATE VIEW data_inventory AS
SELECT
  symbol,
  timeframe,
  feed,
  COUNT(*)                            AS bar_count,
  MIN(ts)::DATE                       AS earliest_date,
  MAX(ts)::DATE                       AS latest_date,
  ROUND(COUNT(*) / 390.0, 1)         AS approx_trading_days,
  MAX(created_at)                     AS last_ingested
FROM ohlcv_bars
GROUP BY symbol, timeframe, feed
ORDER BY symbol, timeframe;

CREATE VIEW options_inventory AS
SELECT
  underlying,
  feed,
  COUNT(DISTINCT ts::DATE)            AS snapshot_days,
  COUNT(*)                            AS total_rows,
  MIN(ts)::DATE                       AS earliest_date,
  MAX(ts)::DATE                       AS latest_date
FROM options_chain
GROUP BY underlying, feed
ORDER BY underlying;

-- Step 2g — Enable pg_cron for partition maintenance
SELECT cron.schedule(
  'partman-maintenance',
  '0 * * * *',
  $$SELECT partman.run_maintenance()$$
);

-- Step 2h — Enable Row Level Security
ALTER TABLE ohlcv_bars       ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_chain    ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_signals      ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_log        ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_results ENABLE ROW LEVEL SECURITY;

-- Service role bypass (for ingestion workers)
CREATE POLICY "service_role_all" ON ohlcv_bars
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON options_chain
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON bot_signals
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON trade_log
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON backtest_results
  FOR ALL TO service_role USING (true);
