-- telegram_outbox: audit trail of every outbound Telegram message.
-- One row is written at the send site for each dispatch attempt, whether it
-- succeeded or failed, so a missing alert is always visible as an explicit row
-- with send_ok = false rather than as silent absence.
--
-- Richard runs this manually in the Supabase cloud dashboard. DO NOT auto-run.

CREATE TABLE telegram_outbox (
  id BIGSERIAL PRIMARY KEY,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  chat_id TEXT NOT NULL,
  message_type TEXT,                 -- 'cycle_report' | 'alert' | 'other'
  body TEXT NOT NULL,
  telegram_message_id BIGINT,
  send_ok BOOLEAN NOT NULL,
  error TEXT
);

CREATE INDEX ON telegram_outbox (sent_at DESC);

ALTER TABLE telegram_outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access"
  ON telegram_outbox
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

