-- Schema Snapshot
-- Last Updated: 2026-07-15

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
  data_provenance text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signal_performance (
  id bigserial PRIMARY KEY,
  symbol text NOT NULL,
  asset_class text,
  signal_type text NOT NULL,
  information_coefficient numeric(8,6),
  win_rate numeric(6,4),
  avg_return numeric(8,6),
  trade_count integer,
  lookback_days integer,
  status text CHECK (status IN ('HEALTHY','DEGRADING','DEAD','INSUFFICIENT_DATA')),
  recommendation text,
  data_provenance text,
  calculated_at timestamptz DEFAULT now()
);
