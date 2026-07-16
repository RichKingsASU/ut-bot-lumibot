-- component_status — per-process heartbeats (ADDITIVE to bot_status).
--
-- The global bot_status row (id=1) cannot detect partial failure: one process
-- can die while another keeps the global heartbeat fresh. Each long-running
-- process upserts its own row here, keyed on process_name, so the watchdog can
-- detect per-process staleness.
--
-- Apply manually (this is NOT created by application code):
--   psql "$SUPABASE_DB_URL" -f dashboard/supabase/component_status.sql
-- or paste into the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS component_status (
  process_name                  TEXT        PRIMARY KEY,   -- 'main', 'run_agents', ...
  last_heartbeat                TIMESTAMPTZ NOT NULL,
  last_successful_cycle_id      BIGINT,                    -- nullable; set by run_agents
  last_trade_decision_timestamp TIMESTAMPTZ,               -- nullable
  status                        TEXT        NOT NULL DEFAULT 'ok',
  updated_at                    TIMESTAMPTZ DEFAULT NOW()
);
