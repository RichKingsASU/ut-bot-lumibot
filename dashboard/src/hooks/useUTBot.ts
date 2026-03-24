import { useMemo } from 'react'
import type { OHLCV, Signal, UTBotResult } from '../types/dashboard'
import { calcATR } from '../utils/atr'
import { calcTrailStop } from '../utils/trailStop'

interface UTBotOptions {
  atrPeriod?: number
  sensitivity?: number
}

export function useUTBot(
  candles: OHLCV[],
  options: UTBotOptions = {}
): UTBotResult & { currentTrailStop: number; currentATR: number; lastSignal: Signal | null } {
  const { atrPeriod = 10, sensitivity = 1.0 } = options

  return useMemo(() => {
    if (candles.length < atrPeriod + 1) {
      return {
        trailStops: [],
        signals: [],
        atr: [],
        currentTrailStop: 0,
        currentATR: 0,
        lastSignal: null,
      }
    }

    const atr = calcATR(candles, atrPeriod)
    const { trailStops, signals } = calcTrailStop(candles, atr, sensitivity)

    const currentTrailStop = trailStops[trailStops.length - 1] ?? 0
    const currentATR = atr[atr.length - 1] ?? 0
    const lastSignal = signals.length > 0 ? signals[signals.length - 1] : null

    return { trailStops, signals, atr, currentTrailStop, currentATR, lastSignal }
  }, [candles, atrPeriod, sensitivity])
}
