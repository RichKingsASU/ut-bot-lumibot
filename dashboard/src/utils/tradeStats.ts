export interface Trade {
  entry: number
  exit: number
  side: 'BUY' | 'SELL'
  pnl: number
  date: string
}

export function calculateWinRate(trades: Trade[]): number {
  if (trades.length === 0) return 0
  const winners = trades.filter((t) => t.pnl > 0).length
  return Math.round((winners / trades.length) * 1000) / 10
}

export function calculateMaxDrawdown(equityValues: number[]): number {
  if (equityValues.length < 2) return 0
  let maxDrawdown = 0
  let peak = equityValues[0]
  for (const val of equityValues) {
    if (val > peak) peak = val
    const drawdown = ((val - peak) / peak) * 100
    if (drawdown < maxDrawdown) maxDrawdown = drawdown
  }
  return Math.round(maxDrawdown * 100) / 100
}

export function calculateSharpe(returns: number[], rfr = 0.05 / 252): number {
  if (returns.length < 2) return 0
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length
  const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length
  const stdDev = Math.sqrt(variance)
  if (stdDev === 0) return 0
  return Math.round(((mean - rfr) / stdDev) * Math.sqrt(252) * 100) / 100
}

export function calculateSortino(returns: number[], rfr = 0.05 / 252): number {
  if (returns.length < 2) return 0
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length
  const downsideReturns = returns.filter((r) => r < rfr)
  if (downsideReturns.length === 0) return 0
  const downsideVariance =
    downsideReturns.reduce((a, r) => a + Math.pow(r - rfr, 2), 0) / downsideReturns.length
  const downsideDev = Math.sqrt(downsideVariance)
  if (downsideDev === 0) return 0
  return Math.round(((mean - rfr) / downsideDev) * Math.sqrt(252) * 100) / 100
}

export function calculateProfitFactor(trades: Trade[]): number {
  const grossProfit = trades.filter((t) => t.pnl > 0).reduce((s, t) => s + t.pnl, 0)
  const grossLoss = Math.abs(trades.filter((t) => t.pnl < 0).reduce((s, t) => s + t.pnl, 0))
  if (grossLoss === 0) return grossProfit > 0 ? Infinity : 0
  return Math.round((grossProfit / grossLoss) * 100) / 100
}

export function sampleSizeWarning(n: number): string | null {
  return n < 30 ? `(n=${n} — insufficient sample for statistical validity)` : null
}
