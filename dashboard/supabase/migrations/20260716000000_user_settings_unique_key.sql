-- ══════════════════════════════════════════════════════════
-- Settings Console wiring: enforce UNIQUE(key) on user_settings
--
-- The dashboard treats user_settings as a key/value store and relies on
-- upsert-on-key (ON CONFLICT (key) DO UPDATE). Without a UNIQUE constraint
-- on `key`, PostgREST upserts default their conflict target to the primary
-- key (id), generate a fresh uuid, attempt a plain INSERT, and — if a row
-- with the same `key` already exists — fail with a duplicate-key error that
-- surfaces to the browser as HTTP 409. This migration makes the constraint
-- explicit so upsert-on-key resolves deterministically.
--
-- Idempotent: safe to run repeatedly. Dedupes any pre-existing duplicate
-- keys (keeping the most recently updated row) before adding the constraint.
-- ══════════════════════════════════════════════════════════

-- 1. Collapse any duplicate keys, keeping the freshest row per key.
DELETE FROM user_settings a
USING user_settings b
WHERE a.key = b.key
  AND a.key IS NOT NULL
  AND (
    a.updated_at < b.updated_at
    OR (a.updated_at IS DISTINCT FROM b.updated_at AND a.updated_at IS NULL AND b.updated_at IS NOT NULL)
    OR (a.updated_at IS NOT DISTINCT FROM b.updated_at AND a.id < b.id)
  );

-- 2. Add the UNIQUE constraint on key if it isn't already present.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'user_settings_key_unique'
  ) THEN
    ALTER TABLE user_settings
      ADD CONSTRAINT user_settings_key_unique UNIQUE (key);
  END IF;
END $$;
