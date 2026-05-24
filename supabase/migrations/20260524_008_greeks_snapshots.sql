CREATE TABLE IF NOT EXISTS greeks_snapshots (
  id bigserial PRIMARY KEY,
  symbol text NOT NULL,
  strike numeric(10,2),
  expiry date,
  option_type text CHECK (option_type IN ('call','put')),
  underlying_price numeric(10,2),
  delta numeric(8,6),
  gamma numeric(8,6),
  theta numeric(8,6),
  vega numeric(8,6),
  iv numeric(8,6),
  iv_rank numeric(5,2),
  rvol numeric(8,4),
  volume integer,
  open_interest integer,
  trade_mode text,
  snapshot_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_greeks_symbol_time
  ON greeks_snapshots (symbol, snapshot_at DESC);
