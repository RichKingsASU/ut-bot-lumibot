-- Add CHECK constraint for the message_type domain.
-- The valid values {cycle_report, alert, other} previously lived only in a
-- code comment; this constraint enforces them at the database level.
--
-- Richard runs this manually in the Supabase cloud dashboard. DO NOT auto-run.

ALTER TABLE telegram_outbox
  ADD CONSTRAINT telegram_outbox_message_type_check
  CHECK (message_type IN ('cycle_report', 'alert', 'other'));
