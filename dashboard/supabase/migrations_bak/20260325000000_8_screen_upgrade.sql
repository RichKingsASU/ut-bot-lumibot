-- strategies table
CREATE TABLE IF NOT EXISTS strategies (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  params      JSONB DEFAULT '{}'::jsonb,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- portfolio_snapshots table
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  equity      NUMERIC(15,2) NOT NULL,
  timestamp   TIMESTAMPTZ DEFAULT NOW(),
  metadata    JSONB DEFAULT '{}'::jsonb
);

-- user_settings table
CREATE TABLE IF NOT EXISTS user_settings (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID UNIQUE,
  settings    JSONB DEFAULT '{}'::jsonb,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Service role policies
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'strategies' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON strategies FOR ALL TO service_role USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'portfolio_snapshots' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON portfolio_snapshots FOR ALL TO service_role USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'user_settings' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON user_settings FOR ALL TO service_role USING (true);
    END IF;
END $$;

-- Real-time
-- Real-time is typically handled by adding tables to the 'supabase_realtime' publication
-- This script ensures they are added if the publication exists.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE strategies;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'strategies table already in publication or error occurred';
        END;
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE portfolio_snapshots;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'portfolio_snapshots table already in publication or error occurred';
        END;
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE user_settings;
        EXCEPTION WHEN others THEN
            RAISE NOTICE 'user_settings table already in publication or error occurred';
        END;
    END IF;
END $$;
