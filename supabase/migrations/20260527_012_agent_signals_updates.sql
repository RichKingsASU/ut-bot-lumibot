-- Migration: 20260527_012_agent_signals_updates
-- Adds new columns required for the pipeline upgrades (Issue 2)

ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS signal_type text;
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS sentiment_trend text;
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS timesfm_forecast text;
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS timesfm_pct numeric(8,4);
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS trade_mode text;
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS iv_rank numeric(5,2);
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS gamma numeric(8,6);
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS sentiment_velocity numeric(8,4);
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS debate_bull_score numeric(5,2);
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS debate_bear_score numeric(5,2);
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS debate_verdict text;
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS kelly_position_value numeric(12,2);
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS regime text;
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS execution_approved boolean;
ALTER TABLE agent_signals ADD COLUMN IF NOT EXISTS macro_approved boolean;

-- Add new columns for signal_log (Issue 3)
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS asset_class text;
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS price numeric(12,4);
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS signal_type text;
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS buy_sig boolean DEFAULT false;
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS sell_sig boolean DEFAULT false;
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS sell_price numeric(12,4);
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS atr numeric(10,6);
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS direction text;
ALTER TABLE signal_log ADD COLUMN IF NOT EXISTS session_id text;

-- Disable Row Level Security on signal_log as per Issue 3
ALTER TABLE signal_log DISABLE ROW LEVEL SECURITY;
