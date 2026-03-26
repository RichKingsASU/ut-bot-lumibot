-- ══════════════════════════════════════════════════════════
-- Streaming data tables for live bot logging
-- bar_log, signal_log, paper_trades, sessions
-- ══════════════════════════════════════════════════════════

-- bar_log: stores 1m bars from the live bot
CREATE TABLE IF NOT EXISTS bar_log (
  id          BIGSERIAL     PRIMARY KEY,
  session_id  TEXT          NOT NULL,
  symbol      TEXT          NOT NULL,
  bar_time    TIMESTAMPTZ   NOT NULL,
  open        NUMERIC(12,4),
  high        NUMERIC(12,4),
  low         NUMERIC(12,4),
  close       NUMERIC(12,4),
  volume      BIGINT,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bar_log_session_time
  ON bar_log (session_id, bar_time DESC);
CREATE INDEX IF NOT EXISTS idx_bar_log_symbol_time
  ON bar_log (symbol, bar_time DESC);

-- signal_log: stores every UT Bot signal
CREATE TABLE IF NOT EXISTS signal_log (
  id           BIGSERIAL     PRIMARY KEY,
  session_id   TEXT          NOT NULL,
  symbol       TEXT          NOT NULL,
  bar_time     TIMESTAMPTZ   NOT NULL,
  timeframe    TEXT          NOT NULL DEFAULT '1D',
  signal_type  TEXT          NOT NULL,
  close_price  NUMERIC(12,4),
  trail_stop   NUMERIC(12,4),
  atr          NUMERIC(12,4),
  rsi          NUMERIC(8,2),
  buy_sig      BOOLEAN,
  sell_sig     BOOLEAN,
  created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_signal_log_session
  ON signal_log (session_id, bar_time DESC);

-- paper_trades: stores both entry and exit rows
CREATE TABLE IF NOT EXISTS paper_trades (
  id                     BIGSERIAL     PRIMARY KEY,
  session_id             TEXT          NOT NULL,
  symbol                 TEXT          NOT NULL,
  contract_symbol        TEXT,
  direction              TEXT,
  option_type            TEXT,
  strike                 NUMERIC(12,4),
  expiration             TEXT,
  qty                    INTEGER,
  side                   TEXT          NOT NULL,
  entry_price            NUMERIC(12,4),
  exit_price             NUMERIC(12,4),
  entry_underlying_price NUMERIC(12,4),
  exit_underlying_price  NUMERIC(12,4),
  trade_pnl              NUMERIC(14,2),
  cumulative_pnl         NUMERIC(14,2),
  exit_reason            TEXT,
  entry_rsi              NUMERIC(8,2),
  created_at             TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_paper_trades_session
  ON paper_trades (session_id, created_at DESC);

-- sessions: tracks bot session lifecycle
CREATE TABLE IF NOT EXISTS sessions (
  id           BIGSERIAL     PRIMARY KEY,
  session_id   TEXT          UNIQUE NOT NULL,
  symbol       TEXT          NOT NULL,
  started_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  ended_at     TIMESTAMPTZ,
  status       TEXT          NOT NULL DEFAULT 'running',
  trades_count INTEGER       DEFAULT 0,
  total_pnl    NUMERIC(14,2) DEFAULT 0,
  metadata     JSONB
);

-- RLS for new tables
ALTER TABLE bar_log       ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_log    ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_trades  ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions      ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON bar_log
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON signal_log
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON paper_trades
  FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON sessions
  FOR ALL TO service_role USING (true);

-- Allow anon read for dashboard
CREATE POLICY "anon_read" ON bar_log
  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON signal_log
  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON paper_trades
  FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read" ON sessions
  FOR SELECT TO anon USING (true);
