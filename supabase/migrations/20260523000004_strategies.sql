-- 20260523_004_strategies.sql
-- Create strategies table + indices + RLS + real-time pub

CREATE TABLE IF NOT EXISTS strategies (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  name text NOT NULL UNIQUE,
  code text,
  status text DEFAULT 'inactive' CHECK (status IN ('active','inactive','testing')),
  deployed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

-- Policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'strategies' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON strategies FOR ALL TO service_role USING (true);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'strategies' AND policyname = 'anon_read') THEN
        CREATE POLICY "anon_read" ON strategies FOR SELECT TO anon USING (true);
    END IF;
END $$;

-- Real-time Publication
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE strategies;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'table strategies already in publication or error occurred';
        END;
    END IF;
END $$;
