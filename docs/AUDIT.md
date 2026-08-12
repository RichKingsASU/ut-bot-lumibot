# Supabase Security & Performance Audit Report

This audit was executed autonomously on the live, linked Supabase project (`disrupting-alpha-lumi` - `wnigkahkamoizjpmpuxs`) using the Supabase CLI, DB Advisors, and direct catalog queries.

## Summary of Findings

| Severity | Count | Description |
| :--- | :---: | :--- |
| **P0 (Critical Security)** | 18 | RLS disabled on sensitive tables, permissive policies, exposed sensitive columns, or insecure views. |
| **P1 (Reliability & Gaps)** | 3 | Excess role privileges/grants, migration drift, and insecure authentication settings. |
| **P2 (Perf & Hygiene)** | 2 | Table bloat, high sequential scan counts on frequently accessed tables. |

---

## Detailed Findings Table

| Priority | Category | Object / Table | Evidence (What we saw) | Proposed Remediation / Fix |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | Security / RLS | `agent_signals`, `bot_status`, `hitl_queue`, `trade_performance`, `signal_performance`, `greeks_snapshots`, `strategies`, `portfolio_snapshots`, `signal_log`, `component_status`, `user_settings`, `news_articles`, `ohlcv_bars_default`, `ohlcv_bars_p20251201` (and other partition tables) | Direct REST query from pg_tables showed `rowsecurity = false`. Anonymous client keys (`anon` role) can read/write directly to these tables. | Enable RLS on all public tables: `ALTER TABLE <name> ENABLE ROW LEVEL SECURITY;`. |
| **P0** | Security / RLS | `risk_config` | Policy `Allow authenticated update access` uses `USING(true) WITH CHECK(true)` for `UPDATE`. | Restrict update access to administrative roles or specific conditions. Remove wildcard permissive rule. |
| **P0** | Security / RLS | `agent_signals`, `bot_status`, `signal_log`, `trade_performance` | Exposed via REST without RLS while containing `session_id` (a sensitive column). | Enable RLS and deny SELECT/INSERT to `anon` role. |
| **P0** | Security / Views | `bar_inventory`, `data_inventory`, `options_inventory`, `options_chain_summary`, `bot_signals` | Defined with `SECURITY DEFINER` property. Queries bypass RLS of calling users and run as owner privileges. | Recreate views with `SECURITY INVOKER` or remove `SECURITY DEFINER` so querying permissions are checked against the active session. |
| **P1** | Security / Grants | All public tables | Direct `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` grants exist for `anon` and `authenticated` roles in `information_schema.role_table_grants`. | Revoke direct modification privileges from public roles (`anon` and `authenticated`) for sensitive tables. Restrict writes to `service_role`. |
| **P1** | Reliability / Git | DB Migration Drift | `supabase migration list --linked` shows remote contains `20260402074233` (not present in local `supabase/migrations/`), while local contains files not recorded on remote `schema_migrations`. | Synchronize the migrations folder. Commit missing remote migrations or baseline the schema correctly. |
| **P1** | Security / Auth | Auth Config | Advisor checked and reported `auth_leaked_password_protection` is disabled. | Enable leaked password protection in the Supabase Dashboard (Auth settings) to check against HaveIBeenPwned. |
| **P2** | Performance | `bot_status`, `paper_trades`, `signal_log` | High count of sequential scans (`bot_status` = 276k, `paper_trades` = 135k) in pg_stat_user_tables. | Tiny tables (1-2 rows) are fine, but ensure queries use primary key indexes to avoid scans. |
| **P2** | Performance | `ohlcv_bars_default`, `news_articles` | Bloat estimates show `ohlcv_bars_default` has 22 MB waste (1.2x bloat), and `news_articles` has 2.4 MB waste (1.2x bloat). | Run `VACUUM FULL` or schedule routine autovacuum maintenance to recover dead tuples. |

---

## Action Plan

### Phase 2: Surgical Fixes (Branch: `fix/supabase-audit-remediation`)
1. **P0/P1 Database Migration**: Create a new timestamped migration `supabase/migrations/20260710000000_supabase_audit_remediation.sql` to:
   - Enable RLS on all tables that have it disabled.
   - Revoke public write grants (`INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`) to `anon` and `authenticated` on sensitive trading tables.
   - Define strict, performance-optimized RLS policies (e.g., using `(select auth.role())` instead of slow dynamic initialization).
   - Recreate views as `SECURITY INVOKER` where possible or ensure they run securely.
2. **P1 Reliability Fix**: Remediate the orchestrator DebateLLM cycle failure mode.
   - Currently, if the Claude API call in `agents/_llm.py` throws an error or runs out of credits, it returns `None`. Let's verify how that propagates in `orchestrator.py` or the debate node, and add structured logging, bounded retries, and a fallback route so cycle heartbeats are always written.
3. **P2 Performance Fix**: Add indexes or clean up duplicate policies.
4. **Gitignore cleanup**: Add `supabase/.temp/*` and virtual environments to `.gitignore`.
