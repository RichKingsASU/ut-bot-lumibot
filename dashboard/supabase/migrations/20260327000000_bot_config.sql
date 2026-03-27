-- bot_config: single source of truth for active instrument + signal parameters
CREATE TABLE IF NOT EXISTS bot_config (
  id           SERIAL PRIMARY KEY,
  key          TEXT UNIQUE NOT NULL,
  value        TEXT NOT NULL,
  updated_at   TIMESTAMPTZ DEFAULT now()
);

INSERT INTO bot_config (key, value) VALUES
  ('active_symbol',   'IWM'),
  ('trade_spy',       'false'),
  ('trade_iwm',       'true'),
  ('trade_qqq',       'false'),
  ('trade_btc',       'false'),
  ('trade_eth',       'false'),
  ('atr_period',      '10'),
  ('atr_mult',        '1.0'),
  ('rsi_period',      '14'),
  ('rsi_oversold',    '30'),
  ('rsi_overbought',  '70'),
  ('paper_mode',      'true')
ON CONFLICT (key) DO NOTHING;
