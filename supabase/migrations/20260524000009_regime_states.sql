-- Migration: 20260524_009_regime_states
-- Description: Create regime_states table to track HMM classified market regimes

CREATE TABLE IF NOT EXISTS regime_states (
  id bigserial PRIMARY KEY,
  symbol text NOT NULL,
  asset_class text NOT NULL,
  regime text NOT NULL CHECK (regime IN ('BULL','BEAR','VOLATILE','QUIET')),
  regime_probability numeric(6,4),
  volatility numeric(8,6),
  trend_strength numeric(8,6),
  volume_ratio numeric(8,4),
  hidden_state integer,
  detected_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_regime_symbol_time
  ON regime_states (symbol, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_regime_detected
  ON regime_states (detected_at DESC);
