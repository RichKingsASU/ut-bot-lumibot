CREATE TABLE hermes_news_feed (
  id TEXT PRIMARY KEY,
  headline TEXT NOT NULL,
  summary TEXT,
  url TEXT,
  source TEXT,
  published_at TIMESTAMPTZ,
  asset_class TEXT CHECK (asset_class IN ('crypto','equities')),
  nats_subject TEXT,
  published_to_nats BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON hermes_news_feed (asset_class, created_at DESC);
CREATE INDEX ON hermes_news_feed (published_at DESC);

CREATE TABLE hermes_observations (
  id BIGSERIAL PRIMARY KEY,
  agent TEXT NOT NULL,
  observation_type TEXT NOT NULL,
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON hermes_observations (agent, created_at DESC);
