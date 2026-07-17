-- 20260523_003_ohlcv_bars.sql
-- Create bar_log table + indices + RLS + real-time pub

CREATE TABLE IF NOT EXISTS bar_log (
  id          BIGSERIAL     PRIMARY KEY,
  session_id  TEXT          NOT NULL,
  symbol      TEXT          NOT NULL,
  bar_time    TIMESTAMPTZ   NOT NULL,
  open        NUMERIC(12,4),
  high        NUMERIC(12,4),
  low         NUMERIC(12,4),
  close       NUMERIC(12,4),
  volume      BIGINT,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Indexing
CREATE INDEX IF NOT EXISTS idx_bar_log_session_time ON bar_log (session_id, bar_time DESC);
CREATE INDEX IF NOT EXISTS idx_bar_log_symbol_time ON bar_log (symbol, bar_time DESC);

-- Enable RLS
ALTER TABLE bar_log ENABLE ROW LEVEL SECURITY;

-- Policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'bar_log' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON bar_log FOR ALL TO service_role USING (true);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'bar_log' AND policyname = 'anon_read') THEN
        CREATE POLICY "anon_read" ON bar_log FOR SELECT TO anon USING (true);
    END IF;
END $$;

-- Real-time Publication
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE bar_log;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'table bar_log already in publication or error occurred';
        END;
    END IF;
END $$;
