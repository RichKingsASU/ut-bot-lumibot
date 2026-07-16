import { useState, useEffect, useRef, useCallback } from 'react'
import type { OHLCV } from '../types/dashboard'
import { netlifyFetch } from '../lib/apiClient'

interface StreamState {
  candles: OHLCV[]
  currentPrice: number
  connected: boolean
  prevClose: number
}

const MAX_CANDLES = 200
const POLL_INTERVAL = 5000
const BARS_INTERVAL = 60000
const MAX_AUTH_FAILURES = 3

function timeframeToMinutes(tf: string): number {
  const map: Record<string, number> = {
    '1m': 1, '5m': 5, '15m': 15, '1h': 60, '1D': 1440,
  }
  return map[tf] ?? 15
}

// Suppress unused-variable warning — kept for potential future use
void timeframeToMinutes

export function useAlpacaStream(symbol: string, timeframe: string): StreamState {
  const [candles, setCandles] = useState<OHLCV[]>([])
  const [currentPrice, setCurrentPrice] = useState(0)
  const [connected, setConnected] = useState(false)
  const [prevClose, setPrevClose] = useState(0)
  const authFailures = useRef(0)
  const stoppedRef = useRef(false)

  const fetchBars = useCallback(async () => {
    if (stoppedRef.current) return
    try {
      const res = await netlifyFetch(
        `alpaca-bars?symbol=${symbol}&timeframe=${timeframe}&limit=${MAX_CANDLES}`
      )
      if (res.status === 401) {
        authFailures.current += 1
        if (authFailures.current >= MAX_AUTH_FAILURES) {
          stoppedRef.current = true
          setConnected(false)
        }
        return
      }
      if (!res.ok) return
      authFailures.current = 0
      const data = await res.json() as { bars: Array<{ t: string; o: number; h: number; l: number; c: number; v: number }> }
      const bars: OHLCV[] = (data.bars || []).map((b) => ({
        time: Math.floor(new Date(b.t).getTime() / 1000),
        open: b.o,
        high: b.h,
        low: b.l,
        close: b.c,
        volume: b.v,
      }))

      if (bars.length >= 2) {
        setPrevClose(bars[bars.length - 2].close)
      }
      if (bars.length > 0) {
        setCurrentPrice(bars[bars.length - 1].close)
      }
      setCandles(bars)
      setConnected(true)
    } catch {
      setConnected(false)
    }
  }, [symbol, timeframe])

  const fetchLatestPrice = useCallback(async () => {
    if (stoppedRef.current) return
    try {
      const res = await netlifyFetch(`alpaca-stream?symbol=${symbol}`)
      if (res.status === 401) {
        authFailures.current += 1
        if (authFailures.current >= MAX_AUTH_FAILURES) {
          stoppedRef.current = true
          setConnected(false)
        }
        return
      }
      if (!res.ok) return
      authFailures.current = 0
      const data = await res.json() as { price?: number }
      if (data.price != null && data.price > 0) {
        setCurrentPrice(data.price)
        setCandles((prev) => {
          if (prev.length === 0) return prev
          const updated = [...prev]
          const last = { ...updated[updated.length - 1] }
          last.close = data.price!
          last.high = Math.max(last.high, data.price!)
          last.low = Math.min(last.low, data.price!)
          updated[updated.length - 1] = last
          return updated
        })
        setConnected(true)
      }
    } catch {
      // silent
    }
  }, [symbol])

  useEffect(() => {
    stoppedRef.current = false
    authFailures.current = 0
    void fetchBars()
    const barsTimer = setInterval(() => {
      if (!stoppedRef.current) void fetchBars()
    }, BARS_INTERVAL)
    const priceTimer = setInterval(() => {
      if (!stoppedRef.current) void fetchLatestPrice()
    }, POLL_INTERVAL)

    return () => {
      clearInterval(barsTimer)
      clearInterval(priceTimer)
    }
  }, [fetchBars, fetchLatestPrice])

  return { candles, currentPrice, connected, prevClose }
}
