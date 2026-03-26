-- Bot status heartbeat table — run in Supabase SQL Editor
CREATE TABLE IF NOT EXISTS bot_status (
  id              INTEGER       PRIMARY KEY DEFAULT 1,
  status          TEXT          NOT NULL DEFAULT 'offline',
  last_heartbeat  TIMESTAMPTZ,
  session_id      TEXT,
  symbol          TEXT,
  mode            TEXT,
  uptime_seconds  INTEGER,
  last_signal     TEXT,
  last_signal_time TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ   DEFAULT NOW()
);

INSERT INTO bot_status (id, status) VALUES (1, 'offline')
  ON CONFLICT DO NOTHING;

ALTER TABLE bot_status ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON bot_status
  FOR ALL TO service_role USING (true);

CREATE POLICY "anon_read" ON bot_status
  FOR SELECT TO anon USING (true);
