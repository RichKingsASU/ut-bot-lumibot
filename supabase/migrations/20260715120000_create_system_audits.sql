-- Migration: 20260715120000_create_system_audits
-- Description: Summary rows for forensic system audits (Track 3 fleet signal audit and successors).
--              One row per audit run; the full report lives at report_path in the repo.

CREATE TABLE IF NOT EXISTS system_audits (
    audit_id text PRIMARY KEY,
    scope text NOT NULL,
    findings_count integer NOT NULL,
    critical_count integer NOT NULL,
    report_path text NOT NULL,
    data_provenance text,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_system_audits_created_at ON system_audits (created_at DESC);
