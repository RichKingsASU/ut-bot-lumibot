-- Migration: 20260524_010_trade_performance
-- Description: Create trade_performance table to track trade history and evaluate Kelly bet sizing win rates

CREATE TABLE IF NOT EXISTS trade_performance (
  id bigserial PRIMARY KEY,
  session_id text,
  symbol text NOT NULL,
  asset_class text,
  signal_type text,
  entry_price numeric(12,4),
  exit_price numeric(12,4),
  pnl numeric(12,4),
  pnl_pct numeric(8,6),
  win boolean,
  hold_bars integer,
  kelly_fraction numeric(6,4),
  position_value numeric(12,2),
  regime_at_entry text,
  iv_rank_at_entry numeric(5,2),
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_perf_symbol
  ON trade_performance (symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_trade_perf_asset_class
  ON trade_performance (asset_class, created_at DESC);
