# Phase 0 — Supabase → GCP dependency inventory

Generated from the live `disrupting-alpha-lumi` project (`wnigkahkamoizjpmpuxs`)
and this repository. Every number below was measured, not estimated.

## Executive summary

Four findings materially reduce the migration program as originally scoped.

| Planned phase | Measured reality | Verdict |
|---|---|---|
| Phase 6/8 — Storage migration (Medium risk) | **0 buckets, 0 code references** | **DELETE THE PHASE** |
| Phase 5 — Auth migration (High risk) | **1 user**, email/password only, no MFA, no OAuth | Downgrade to Low |
| Phase 6 — RLS → API authorization (High risk) | All 60 policies are **role-based** (`auth.role()`), zero per-user (`auth.uid()`) row ownership | Downgrade to Medium |
| Phase 10 — Supabase Edge Functions → Cloud Run | **No Supabase Edge Functions exist.** 29 **Netlify** Functions instead | Retarget: Netlify → Cloud Run |

The serverless finding is the one that changes work, not just risk. The plan
assumed `supabase/functions/`; that directory does not exist. The actual
serverless tier is Netlify, a different vendor with a different deployment
model, auth story, and cutover path. It is also where most `createClient` calls
live, so it — not the React app — is the real coupling surface.

## Scope at a glance

- 35 tables/views exposed via PostgREST
- 23 tables carry RLS policies (60 policies; grants: 27 service_role, 26 authenticated, 6 anon, 2 public)
- 23 SQL migration files
- 19 files construct a Supabase client; 29 Netlify functions
- 3 tables have realtime subscriptions, via a single React hook
- 1 auth user, 0 storage buckets

## Gate 0 status

Inventory exists. **Not yet complete** — see "Known gaps" in `database.md`.
Sequencing note: `da-gcp-replicator` has still never replicated a row, so
Phase 1 of the migration has no proven foundation yet.
