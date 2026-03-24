import type { OHLCV, Signal } from '../types/dashboard'

/**
 * UT Bot ATR Trailing Stop
 * Exactly as specified in the brief
 */
export function calcTrailStop(
  candles: OHLCV[],
  atr: number[],
  sensitivity: number
): { trailStops: number[]; signals: Signal[] } {
  const n = candles.length
  const trailStops: number[] = new Array(n).fill(0)
  const signals: Signal[] = []

  if (n < 2) return { trailStops, signals }

  // Find the first valid ATR index
  let startIdx = 0
  for (let i = 0; i < n; i++) {
    if (atr[i] > 0) { startIdx = i; break }
  }

  // Initialize first trail stop
  const loss0 = sensitivity * atr[startIdx]
  trailStops[startIdx] = candles[startIdx].close > 0
    ? candles[startIdx].close - loss0
    : 0

  for (let i = startIdx + 1; i < n; i++) {
    const loss = sensitivity * atr[i]
    const close = candles[i].close
    const prevClose = candles[i - 1].close
    const prev = trailStops[i - 1]

    let ts: number
    if (close > prev && prevClose > prev) {
      ts = Math.max(prev, close - loss)
    } else if (close < prev && prevClose < prev) {
      ts = Math.min(prev, close + loss)
    } else if (close > prev) {
      ts = close - loss
    } else {
      ts = close + loss
    }
    trailStops[i] = ts

    // Signal detection via crossover
    if (close > ts && prevClose <= trailStops[i - 1]) {
      signals.push({ index: i, type: 'BUY', price: close, time: candles[i].time })
    } else if (close < ts && prevClose >= trailStops[i - 1]) {
      signals.push({ index: i, type: 'SELL', price: close, time: candles[i].time })
    }
  }

  return { trailStops, signals }
}
