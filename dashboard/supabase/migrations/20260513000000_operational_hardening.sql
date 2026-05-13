-- ══════════════════════════════════════════════════════════
-- Operational Hardening: Alerts and Audit Trail
-- system_alerts, system_audit
-- ══════════════════════════════════════════════════════════

-- system_alerts: Real-time system notifications for operator attention
CREATE TABLE IF NOT EXISTS system_alerts (
  id          BIGSERIAL     PRIMARY KEY,
  session_id  TEXT          NOT NULL,
  ts          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  level       TEXT          NOT NULL, -- INFO, WARNING, ERROR, CRITICAL
  category    TEXT          NOT NULL, -- RISK, INFRASTRUCTURE, STRATEGY, SECURITY
  message     TEXT          NOT NULL,
  metadata    JSONB         DEFAULT '{}',
  is_resolved BOOLEAN       DEFAULT FALSE,
  resolved_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_system_alerts_session ON system_alerts (session_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_system_alerts_unresolved ON system_alerts (is_resolved) WHERE is_resolved = FALSE;

-- system_audit: High-integrity audit trail for major system events
CREATE TABLE IF NOT EXISTS system_audit (
  id          BIGSERIAL     PRIMARY KEY,
  session_id  TEXT          NOT NULL,
  ts          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  action      TEXT          NOT NULL, -- START, STOP, SYNC, FLATTEN, RECOVER
  status      TEXT          NOT NULL, -- SUCCESS, FAILURE, LOGGED
  details     TEXT,
  metadata    JSONB         DEFAULT '{}',
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_system_audit_session ON system_audit (session_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_system_audit_action ON system_audit (action);

-- Enable RLS
ALTER TABLE system_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_audit ENABLE ROW LEVEL SECURITY;

-- service_role: Full access
CREATE POLICY "service_role_all" ON system_alerts FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON system_audit FOR ALL TO service_role USING (true);

-- anon/authenticated: Read access for dashboard
CREATE POLICY "dashboard_read" ON system_alerts FOR SELECT TO authenticated USING (true);
CREATE POLICY "dashboard_read" ON system_audit FOR SELECT TO authenticated USING (true);

-- Support anon read for dev (matching existing patterns)
CREATE POLICY "anon_read" ON system_alerts FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON system_audit FOR SELECT TO anon USING (true);
