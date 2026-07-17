-- Add expires_at and expired boolean
ALTER TABLE hitl_queue
ADD COLUMN IF NOT EXISTS expires_at timestamptz DEFAULT (now() + interval '15 minutes'),
ADD COLUMN IF NOT EXISTS expired boolean DEFAULT false;

-- Add a pg_cron job to mark rows as expired
SELECT cron.schedule(
    'hitl_queue_expire_job',
    '* * * * *',
    $$
    UPDATE hitl_queue 
    SET expired = true 
    WHERE approved = false 
      AND rejected = false 
      AND executed = false 
      AND expired = false 
      AND now() > expires_at;
    $$
);
