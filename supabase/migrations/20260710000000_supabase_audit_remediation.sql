-- 20260710000000_supabase_audit_remediation.sql
-- Idempotent Supabase security audit remediation migration

-- 1. Enable Row Level Security (RLS) on all exposed tables
ALTER TABLE IF EXISTS ohlcv_bars_p20251201 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ohlcv_bars_p20260101 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ohlcv_bars_p20260201 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ohlcv_bars_p20260301 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ohlcv_bars_p20260401 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ohlcv_bars_p20260501 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ohlcv_bars_p20260601 ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ohlcv_bars_default ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS regime_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS trade_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS signal_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS greeks_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS portfolio_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS signal_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS component_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS news_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS bot_status ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS hitl_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS agent_signals ENABLE ROW LEVEL SECURITY;

-- 2. Revoke public/anon write and truncate grants on sensitive tables
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE 
  regime_states, 
  trade_performance, 
  signal_performance, 
  greeks_snapshots, 
  strategies, 
  portfolio_snapshots, 
  signal_log, 
  component_status, 
  user_settings, 
  bot_status, 
  hitl_queue, 
  agent_signals,
  component_heartbeat,
  sessions,
  paper_trades,
  trade_log,
  risk_config,
  system_alerts
FROM anon;

REVOKE TRUNCATE, DELETE ON TABLE 
  regime_states, 
  trade_performance, 
  signal_performance, 
  greeks_snapshots, 
  strategies, 
  portfolio_snapshots, 
  signal_log, 
  component_status, 
  user_settings, 
  bot_status, 
  hitl_queue, 
  agent_signals,
  component_heartbeat,
  sessions,
  paper_trades,
  trade_log,
  risk_config,
  system_alerts
FROM authenticated;

REVOKE INSERT, UPDATE ON TABLE
  trade_log,
  component_status,
  component_heartbeat,
  bot_status,
  regime_states,
  greeks_snapshots,
  portfolio_snapshots,
  trade_performance,
  signal_performance,
  agent_signals
FROM authenticated;

-- 3. Define least-privilege, optimized RLS policies
-- Helper: Wrap auth calls inside (select auth.role()) inside policies for performance

-- agent_signals
DROP POLICY IF EXISTS "service_role_all" ON agent_signals;
CREATE POLICY "service_role_all" ON agent_signals FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON agent_signals;
CREATE POLICY "authenticated_read" ON agent_signals FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- bot_status
DROP POLICY IF EXISTS "service_role_all" ON bot_status;
CREATE POLICY "service_role_all" ON bot_status FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON bot_status;
CREATE POLICY "authenticated_read" ON bot_status FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- hitl_queue
DROP POLICY IF EXISTS "service_role_all" ON hitl_queue;
CREATE POLICY "service_role_all" ON hitl_queue FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON hitl_queue;
CREATE POLICY "authenticated_read" ON hitl_queue FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "authenticated_write" ON hitl_queue;
CREATE POLICY "authenticated_write" ON hitl_queue FOR UPDATE TO authenticated USING ( (select auth.role()) = 'authenticated' ) WITH CHECK ( (select auth.role()) = 'authenticated' );

-- trade_performance
DROP POLICY IF EXISTS "service_role_all" ON trade_performance;
CREATE POLICY "service_role_all" ON trade_performance FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON trade_performance;
CREATE POLICY "authenticated_read" ON trade_performance FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- signal_performance
DROP POLICY IF EXISTS "service_role_all" ON signal_performance;
CREATE POLICY "service_role_all" ON signal_performance FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON signal_performance;
CREATE POLICY "authenticated_read" ON signal_performance FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- greeks_snapshots
DROP POLICY IF EXISTS "service_role_all" ON greeks_snapshots;
CREATE POLICY "service_role_all" ON greeks_snapshots FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON greeks_snapshots;
CREATE POLICY "authenticated_read" ON greeks_snapshots FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- strategies
DROP POLICY IF EXISTS "service_role_all" ON strategies;
CREATE POLICY "service_role_all" ON strategies FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON strategies;
CREATE POLICY "authenticated_read" ON strategies FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "authenticated_write" ON strategies;
CREATE POLICY "authenticated_write" ON strategies FOR ALL TO authenticated USING ( (select auth.role()) = 'authenticated' ) WITH CHECK ( (select auth.role()) = 'authenticated' );

-- portfolio_snapshots
DROP POLICY IF EXISTS "service_role_all" ON portfolio_snapshots;
CREATE POLICY "service_role_all" ON portfolio_snapshots FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON portfolio_snapshots;
CREATE POLICY "authenticated_read" ON portfolio_snapshots FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- signal_log
DROP POLICY IF EXISTS "service_role_all" ON signal_log;
CREATE POLICY "service_role_all" ON signal_log FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON signal_log;
CREATE POLICY "authenticated_read" ON signal_log FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "anon_read" ON signal_log;

-- component_status
DROP POLICY IF EXISTS "service_role_all" ON component_status;
CREATE POLICY "service_role_all" ON component_status FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON component_status;
CREATE POLICY "authenticated_read" ON component_status FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- component_heartbeat
DROP POLICY IF EXISTS "service_role_all" ON component_heartbeat;
CREATE POLICY "service_role_all" ON component_heartbeat FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON component_heartbeat;
CREATE POLICY "authenticated_read" ON component_heartbeat FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "Allow public read access to component_heartbeat" ON component_heartbeat;

-- user_settings
DROP POLICY IF EXISTS "service_role_all" ON user_settings;
CREATE POLICY "service_role_all" ON user_settings FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON user_settings;
CREATE POLICY "authenticated_read" ON user_settings FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "authenticated_write" ON user_settings;
CREATE POLICY "authenticated_write" ON user_settings FOR ALL TO authenticated USING ( (select auth.role()) = 'authenticated' ) WITH CHECK ( (select auth.role()) = 'authenticated' );

-- regime_states
DROP POLICY IF EXISTS "service_role_all" ON regime_states;
CREATE POLICY "service_role_all" ON regime_states FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON regime_states;
CREATE POLICY "authenticated_read" ON regime_states FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- sessions
DROP POLICY IF EXISTS "service_role_all" ON sessions;
CREATE POLICY "service_role_all" ON sessions FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON sessions;
CREATE POLICY "authenticated_read" ON sessions FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "anon_read" ON sessions;

-- paper_trades
DROP POLICY IF EXISTS "service_role_all" ON paper_trades;
CREATE POLICY "service_role_all" ON paper_trades FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON paper_trades;
CREATE POLICY "authenticated_read" ON paper_trades FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "anon_read" ON paper_trades;

-- risk_config
DROP POLICY IF EXISTS "service_role_all" ON risk_config;
CREATE POLICY "service_role_all" ON risk_config FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "Allow authenticated read access" ON risk_config;
DROP POLICY IF EXISTS "authenticated_read" ON risk_config;
CREATE POLICY "authenticated_read" ON risk_config FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "Allow authenticated update access" ON risk_config;
DROP POLICY IF EXISTS "authenticated_write" ON risk_config;
CREATE POLICY "authenticated_write" ON risk_config FOR UPDATE TO authenticated USING ( (select auth.role()) = 'authenticated' ) WITH CHECK ( (select auth.role()) = 'authenticated' );

-- system_alerts
DROP POLICY IF EXISTS "service_role_all" ON system_alerts;
CREATE POLICY "service_role_all" ON system_alerts FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "dashboard_read" ON system_alerts;
DROP POLICY IF EXISTS "authenticated_read" ON system_alerts;
CREATE POLICY "authenticated_read" ON system_alerts FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "authenticated_write" ON system_alerts;
CREATE POLICY "authenticated_write" ON system_alerts FOR UPDATE TO authenticated USING ( (select auth.role()) = 'authenticated' ) WITH CHECK ( (select auth.role()) = 'authenticated' );
DROP POLICY IF EXISTS "anon_read" ON system_alerts;

-- news_articles
DROP POLICY IF EXISTS "service_role_all" ON news_articles;
CREATE POLICY "service_role_all" ON news_articles FOR ALL TO service_role USING (true);
DROP POLICY IF EXISTS "authenticated_read" ON news_articles;
CREATE POLICY "authenticated_read" ON news_articles FOR SELECT TO authenticated USING ( (select auth.role()) = 'authenticated' );

-- 4. Enable security_invoker = on on views to enforce user RLS policies on query execution
ALTER VIEW IF EXISTS bar_inventory SET (security_invoker = on);
ALTER VIEW IF EXISTS data_inventory SET (security_invoker = on);
ALTER VIEW IF EXISTS options_inventory SET (security_invoker = on);
ALTER VIEW IF EXISTS options_chain_summary SET (security_invoker = on);
ALTER VIEW IF EXISTS bot_signals SET (security_invoker = on);
