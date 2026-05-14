-- ══════════════════════════════════════════════════════════
-- Production Security Hardening: Revoke Public Access
-- system_alerts, system_audit
-- ══════════════════════════════════════════════════════════

-- Remove public (anon) read access from sensitive operational tables
DROP POLICY IF EXISTS "anon_read" ON system_alerts;
DROP POLICY IF EXISTS "anon_read" ON system_audit;

-- Ensure only authenticated users with a valid session can view health/audits
-- This is a critical step for moving from 'demo' to 'pilot'
ALTER TABLE system_alerts FORCE ROW LEVEL SECURITY;
ALTER TABLE system_audit FORCE ROW LEVEL SECURITY;

-- Note: 'authenticated' users are those logged into the Supabase Dashboard
-- In a multi-tenant setup, we would further restrict by user_id.
