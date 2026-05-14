-- ══════════════════════════════════════════════════════════
-- Remote Command & Control (C2): Bot Control
-- bot_status
-- ══════════════════════════════════════════════════════════

-- Add target_status column to allow dashboard to signal the bot
ALTER TABLE bot_status ADD COLUMN IF NOT EXISTS target_status TEXT DEFAULT 'running';

-- Add a comment for operator clarity
COMMENT ON COLUMN bot_status.target_status IS 'Dashboard signals: running, shutdown, restart';

-- Ensure only authenticated users can write commands
-- The service_role (bot) will have full access.
CREATE POLICY "operator_control" ON bot_status
  FOR UPDATE TO authenticated
  USING (id = 1)
  WITH CHECK (id = 1);
