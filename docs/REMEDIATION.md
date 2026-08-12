# Supabase Remediation Report

This report outlines the surgical fixes applied to address the security, reliability, and performance issues identified in the Supabase audit. All changes are staged in the `fix/supabase-audit-remediation` branch.

## Audit Findings vs. Remediation Changes

| Category | Finding | Applied Remediation | Code Location |
| :--- | :--- | :--- | :--- |
| **P0 Security** | RLS disabled on 21 public tables and partitions | Enabled RLS on all tables and partitions explicitly. | [20260710000000_supabase_audit_remediation.sql](file:///c:/Users/Richa/ut-bot-lumibot/supabase/migrations/20260710000000_supabase_audit_remediation.sql) |
| **P0 Security** | Insecure SECURITY DEFINER views | Altered views to use `security_invoker = on`, ensuring queries respect user session permissions. | [20260710000000_supabase_audit_remediation.sql](file:///c:/Users/Richa/ut-bot-lumibot/supabase/migrations/20260710000000_supabase_audit_remediation.sql) |
| **P0 Security** | Insecure RLS update policy on `risk_config` | Dropped the permissive `USING(true)` policy and created a secure, optimized role-check policy. | [20260710000000_supabase_audit_remediation.sql](file:///c:/Users/Richa/ut-bot-lumibot/supabase/migrations/20260710000000_supabase_audit_remediation.sql) |
| **P1 Security** | Wildcard table-level grants to public roles | Revoked `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` privileges from `anon` on all sensitive tables, and restricted `authenticated` writes. | [20260710000000_supabase_audit_remediation.sql](file:///c:/Users/Richa/ut-bot-lumibot/supabase/migrations/20260710000000_supabase_audit_remediation.sql) |
| **P1 Reliability** | DebateLLM API failures stall trading loop | Added structured error classification (fail-fast vs backoff), bounded retries with backoff, and 15s timeout. | [_llm.py](file:///c:/Users/Richa/ut-bot-lumibot/agents/_llm.py) |
| **P1 Reliability** | Orchestrator pipeline crash stops heartbeats | Wrapped graph invocations in try-except blocks, returning a default degraded state so the loop finishes and heartbeats are posted. | [orchestrator.py](file:///c:/Users/Richa/ut-bot-lumibot/agents/orchestrator.py) |
| **P1 Hygiene** | Local CLI temporary files and venv debris untracked | Updated gitignore to exclude `supabase/.temp/*` and the broken environment. | [.gitignore](file:///c:/Users/Richa/ut-bot-lumibot/.gitignore) |

---

## Manual Steps (For Deployment & Maintenance)

### 1. Execute SQL Migration on Production DB
Once you review and approve the branch, apply the migration to the production instance using the Supabase CLI:
```powershell
supabase db push
```

### 2. Configure Database/API Keys Rotation
No credentials should ever be committed to git. Ensure the following environment variables are securely stored in your production environment (Netlify environment variables and VM `.env` file):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY_AGENTS`
- `ANTHROPIC_API_KEY_SENTIMENT`
- `ANTHROPIC_API_KEY_HERMES`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

If rotation of keys is performed:
1. In the Supabase Dashboard -> Project Settings -> API, click "Rotate Key" for the `service_role` key.
2. Update the environment variables in Netlify, the VM host, and any local `.env` files immediately.
3. Restart the background processes (e.g. TMUX sessions) to load the new keys.

### 3. Verify Heartbeat Watchdog Status
Confirm the tmux background loops are running:
```powershell
tmux list-sessions
```
And check components heartbeat status directly in Supabase to ensure everything is reporting `OK` or `DEGRADED` (and not stale).
