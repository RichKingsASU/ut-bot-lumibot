-- Migration: 20260524_011_signal_performance
-- Description: Create signal_performance table and indexes to track signal decay and Information Coefficient (IC)

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
  calculated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signal_perf_symbol
  ON signal_performance (symbol, calculated_at DESC);

CREATE INDEX IF NOT EXISTS idx_signal_perf_status
  ON signal_performance (status, calculated_at DESC);
