ALTER TABLE hitl_queue
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ
  DEFAULT NOW() + INTERVAL '15 minutes',
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'PROPOSED';

UPDATE hitl_queue SET status = 'EXECUTED' WHERE executed = true;
UPDATE hitl_queue SET status = 'REJECTED' WHERE rejected = true;
UPDATE hitl_queue SET status = 'APPROVED' WHERE approved = true;
UPDATE hitl_queue SET status = 'PROPOSED'
  WHERE status IS NULL;

SELECT cron.schedule(
  'expire-hitl-signals',
  '* * * * *',
  $$
  UPDATE hitl_queue
  SET status = 'EXPIRED'
  WHERE status = 'PROPOSED'
  AND expires_at < NOW();
  $$
);
