-- 20260523_005_portfolio_snapshots.sql
-- Create portfolio_snapshots table + indices + RLS + real-time pub

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id bigserial PRIMARY KEY,
  equity numeric(18,2) NOT NULL,
  buying_power numeric(18,2),
  cash numeric(18,2),
  positions jsonb DEFAULT '[]',
  daily_pnl numeric(18,2),
  snapshot_at timestamptz DEFAULT now()
);

-- Indexing
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_time
  ON portfolio_snapshots (snapshot_at DESC);

-- Enable RLS
ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;

-- Policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'portfolio_snapshots' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON portfolio_snapshots FOR ALL TO service_role USING (true);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'portfolio_snapshots' AND policyname = 'anon_read') THEN
        CREATE POLICY "anon_read" ON portfolio_snapshots FOR SELECT TO anon USING (true);
    END IF;
END $$;

-- Real-time Publication
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE portfolio_snapshots;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'table portfolio_snapshots already in publication or error occurred';
        END;
    END IF;
END $$;
