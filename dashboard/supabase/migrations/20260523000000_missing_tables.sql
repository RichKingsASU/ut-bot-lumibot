-- strategies table (required by StrategyLab and dashboard)
CREATE TABLE IF NOT EXISTS strategies (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  name text NOT NULL UNIQUE,
  code text,
  status text DEFAULT 'inactive'
    CHECK (status IN ('active','inactive','testing')),
  deployed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- portfolio_snapshots (required by Portfolio equity curve)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id bigserial PRIMARY KEY,
  equity numeric(18,2) NOT NULL,
  buying_power numeric(18,2),
  cash numeric(18,2),
  positions jsonb DEFAULT '[]',
  daily_pnl numeric(18,2),
  snapshot_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_time
  ON portfolio_snapshots (snapshot_at DESC);

-- bot_signals consolidation (dashboard reads bot_signals
-- but bot writes to signal_log — create a view to bridge)
CREATE OR REPLACE VIEW bot_signals AS
  SELECT
    id,
    session_id,
    symbol,
    bar_time as timestamp,
    signal_type,
    close_price as price,
    trail_stop,
    atr,
    rsi,
    buy_sig,
    sell_sig,
    created_at
  FROM signal_log;
