import type { OHLCV } from '../types/dashboard'

/**
 * Calculate Average True Range (ATR)
 * Returns array same length as candles; first (period-1) values are 0
 */
export function calcATR(candles: OHLCV[], period: number): number[] {
  if (candles.length === 0) return []

  const trueRanges: number[] = [0]

  for (let i = 1; i < candles.length; i++) {
    const cur = candles[i]
    const prev = candles[i - 1]
    const tr = Math.max(
      cur.high - cur.low,
      Math.abs(cur.high - prev.close),
      Math.abs(cur.low - prev.close)
    )
    trueRanges.push(tr)
  }

  const atr: number[] = new Array(candles.length).fill(0)

  if (candles.length < period) return atr

  // Initial ATR = simple average of first `period` true ranges
  let sum = 0
  for (let i = 0; i < period; i++) sum += trueRanges[i]
  atr[period - 1] = sum / period

  // Wilder's smoothing
  for (let i = period; i < candles.length; i++) {
    atr[i] = (atr[i - 1] * (period - 1) + trueRanges[i]) / period
  }

  return atr
}
