-- 20260523_006_news.sql
-- Create news_articles table + indices + RLS + real-time pub

CREATE TABLE IF NOT EXISTS news_articles (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  url text NOT NULL UNIQUE,
  source text,
  published_at timestamptz NOT NULL,
  summary text,
  sentiment_score numeric(4,2),
  created_at timestamptz DEFAULT now()
);

-- Indexing
CREATE INDEX IF NOT EXISTS idx_news_articles_published ON news_articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_articles_url ON news_articles (url);

-- Enable RLS
ALTER TABLE news_articles ENABLE ROW LEVEL SECURITY;

-- Policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'news_articles' AND policyname = 'service_role_all') THEN
        CREATE POLICY "service_role_all" ON news_articles FOR ALL TO service_role USING (true);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'news_articles' AND policyname = 'anon_read') THEN
        CREATE POLICY "anon_read" ON news_articles FOR SELECT TO anon USING (true);
    END IF;
END $$;

-- Real-time Publication
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE news_articles;
        EXCEPTION
            WHEN others THEN
                RAISE NOTICE 'table news_articles already in publication or error occurred';
        END;
    END IF;
END $$;
