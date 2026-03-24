// Dashboard State Types

import type { AlpacaAccount, AlpacaPosition, AlpacaOrder, AlpacaBar } from './alpaca'

export interface OHLCV {
  time: number // Unix timestamp (seconds)
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface Signal {
  index: number
  type: 'BUY' | 'SELL'
  price: number
  time: number
}

export interface UTBotResult {
  trailStops: number[]
  signals: Signal[]
  atr: number[]
}

export interface DashboardState {
  symbol: string
  timeframe: string
  currentPrice: number
  prevClose: number
  priceChange: number
  priceChangePct: number
  candles: OHLCV[]
  account: AlpacaAccount | null
  positions: AlpacaPosition[]
  orders: AlpacaOrder[]
  isInTrade: boolean
  activePosition: AlpacaPosition | null
  botRunning: boolean
  marketStatus: 'OPEN' | 'CLOSED' | 'PRE' | 'AFTER'
  connected: boolean
  loading: boolean
  error: string | null
  logs: LogEntry[]
}

export interface LogEntry {
  id: string
  timestamp: Date
  message: string
  level: 'info' | 'warning' | 'error' | 'success'
}

export interface IndicatorState {
  atrStop: boolean
  signals: boolean
  volume: boolean
  srLines: boolean
  ema9: boolean
  ema21: boolean
  vwap: boolean
  rsi: boolean
  macd: boolean
  bollinger: boolean
}

export type Timeframe = '1m' | '5m' | '15m' | '1h' | '1D'

export interface OHLCBarData {
  open: number
  high: number
  low: number
  close: number
  volume: number
  time: string
}
