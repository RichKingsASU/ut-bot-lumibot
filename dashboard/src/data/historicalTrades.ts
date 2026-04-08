// Single source of truth for historical equities trade history. Both
// Overview (Win Rate card) and Performance (KPI cards + table) read from
// here so the same number is shown in both places.
//
// TODO: replace with a Supabase query once the paper_trades table is wired
// up. For now this matches the previously hardcoded mockTrades from
// EquitiesPerformanceView so the displayed numbers stay consistent.
export interface HistoricalTrade {
  date: string
  symbol: string
  side: 'BUY' | 'SELL'
  entry: number
  exit: number
  pnl: number
  returnPct: number
}

export const HISTORICAL_TRADES: HistoricalTrade[] = [
  { date: '2026-03-25', symbol: 'IWM', side: 'BUY',  entry: 202.35, exit: 205.12, pnl:  277.0, returnPct:  1.37 },
  { date: '2026-03-24', symbol: 'SPY', side: 'BUY',  entry: 512.80, exit: 515.40, pnl:  260.0, returnPct:  0.51 },
  { date: '2026-03-21', symbol: 'IWM', side: 'SELL', entry: 208.50, exit: 205.90, pnl:  260.0, returnPct:  1.25 },
  { date: '2026-03-19', symbol: 'QQQ', side: 'BUY',  entry: 438.20, exit: 436.10, pnl: -210.0, returnPct: -0.48 },
  { date: '2026-03-17', symbol: 'IWM', side: 'BUY',  entry: 199.10, exit: 202.80, pnl:  370.0, returnPct:  1.86 },
  { date: '2026-03-14', symbol: 'SPY', side: 'SELL', entry: 518.60, exit: 516.20, pnl:  240.0, returnPct:  0.46 },
  { date: '2026-03-12', symbol: 'IWM', side: 'BUY',  entry: 196.40, exit: 194.80, pnl: -160.0, returnPct: -0.81 },
  { date: '2026-03-10', symbol: 'QQQ', side: 'BUY',  entry: 432.50, exit: 437.30, pnl:  480.0, returnPct:  1.11 },
  { date: '2026-03-07', symbol: 'IWM', side: 'SELL', entry: 204.70, exit: 201.90, pnl:  280.0, returnPct:  1.37 },
  { date: '2026-03-05', symbol: 'SPY', side: 'BUY',  entry: 508.90, exit: 511.60, pnl:  270.0, returnPct:  0.53 },
]

/** All-time win rate computed from the historical trade log (0–100, integer). */
export function calculateAllTimeWinRate(trades: HistoricalTrade[] = HISTORICAL_TRADES): number {
  if (trades.length === 0) return 0
  const wins = trades.filter(t => t.pnl > 0).length
  return Math.round((wins / trades.length) * 100)
}
