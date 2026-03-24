// Alpaca API Response Types

export interface AlpacaAccount {
  id: string
  account_number: string
  status: string
  currency: string
  cash: string
  portfolio_value: string
  non_marginable_buying_power: string
  buying_power: string
  equity: string
  last_equity: string
  long_market_value: string
  short_market_value: string
  initial_margin: string
  maintenance_margin: string
  last_maintenance_margin: string
  sma: string
  daytrade_count: number
  pattern_day_trader: boolean
  trading_blocked: boolean
  transfers_blocked: boolean
  account_blocked: boolean
  created_at: string
  shorting_enabled: boolean
  multiplier: string
  unrealized_pl: string
  unrealized_plpc: string
  realized_pl: string
  realized_plpc: string
}

export interface AlpacaPosition {
  asset_id: string
  symbol: string
  exchange: string
  asset_class: string
  asset_marginable: boolean
  avg_entry_price: string
  qty: string
  qty_available: string
  side: 'long' | 'short'
  market_value: string
  cost_basis: string
  unrealized_pl: string
  unrealized_plpc: string
  unrealized_intraday_pl: string
  unrealized_intraday_plpc: string
  current_price: string
  lastday_price: string
  change_today: string
  swap_rate: string | null
  usd_qty: string | null
  avg_entry_swap_rate: string | null
  usd_market_value: string | null
  usd_pl: string | null
  usd_plpc: string | null
  usd_cost_basis: string | null
}

export interface AlpacaOrder {
  id: string
  client_order_id: string
  created_at: string
  updated_at: string
  submitted_at: string
  filled_at: string | null
  expired_at: string | null
  canceled_at: string | null
  failed_at: string | null
  replaced_at: string | null
  replaced_by: string | null
  replaces: string | null
  asset_id: string
  symbol: string
  asset_class: string
  notional: string | null
  qty: string
  filled_qty: string
  filled_avg_price: string | null
  order_class: string
  order_type: string
  type: string
  side: 'buy' | 'sell'
  time_in_force: string
  limit_price: string | null
  stop_price: string | null
  status: string
  extended_hours: boolean
  legs: AlpacaOrder[] | null
  trail_percent: string | null
  trail_price: string | null
  hwm: string | null
}

export interface AlpacaBar {
  t: string // ISO timestamp
  o: number // open
  h: number // high
  l: number // low
  c: number // close
  v: number // volume
}

export interface AlpacaTrade {
  t: string
  p: number // price
  s: number // size
  x: string // exchange
  i: number // trade id
  c: string[] // conditions
  z: string // tape
}

export interface AlpacaStreamMessage {
  T: string
  msg?: string
  code?: number
  [Symbol: string]: unknown
}
