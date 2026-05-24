-- 20260523_002_paper_trades.sql
-- Create paper_trades table + indices + RLS + real-time pub

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

-- Indexing
CREATE INDEX IF NOT EXISTS idx_paper_trades_session_time
  ON paper_trades (session_id, created_at DESC);

-- Enable RLS
ALTER TABLE paper_trades ENABLE ROW LEVEL SECURITY;

-- Policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'paper_trades' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON paper_trades FOR ALL TO service_role USING (true);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'paper_trades' AND policyname = 'anon_read') THEN
        CREATE POLICY "anon_read" ON paper_trades FOR SELECT TO anon USING (true);
    END IF;
END $$;

-- Real-time Publication
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE paper_trades;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'table paper_trades already in publication or error occurred';
        END;
    END IF;
END $$;
