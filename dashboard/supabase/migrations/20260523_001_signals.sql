-- 20260523_001_signals.sql
-- Create signal_log table + indices + RLS + real-time pub

CREATE TABLE IF NOT EXISTS signal_log (
  id           BIGSERIAL     PRIMARY KEY,
  session_id   TEXT          NOT NULL,
  symbol       TEXT          NOT NULL,
  bar_time     TIMESTAMPTZ   NOT NULL,
  timeframe    TEXT          NOT NULL DEFAULT '1D',
  signal_type  TEXT          NOT NULL,
  close_price  NUMERIC(12,4),
  trail_stop   NUMERIC(12,4),
  atr          NUMERIC(12,4),
  rsi          NUMERIC(8,2),
  buy_sig      BOOLEAN,
  sell_sig     BOOLEAN,
  created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Indexing
CREATE INDEX IF NOT EXISTS idx_signal_log_session_time 
  ON signal_log (session_id, bar_time DESC);

-- Enable RLS
ALTER TABLE signal_log ENABLE ROW LEVEL SECURITY;

-- Policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'signal_log' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON signal_log FOR ALL TO service_role USING (true);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'signal_log' AND policyname = 'anon_read') THEN
        CREATE POLICY "anon_read" ON signal_log FOR SELECT TO anon USING (true);
    END IF;
END $$;

-- Real-time Publication
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE signal_log;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'table signal_log already in publication or error occurred';
        END;
    END IF;
END $$;
