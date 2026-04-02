import { useState, useEffect, useCallback } from 'react'

interface Bar {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface UseAlpacaBarsResult {
  bars: Bar[]
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useAlpacaBars(symbol: string, timeframe: string, limit = 200): UseAlpacaBarsResult {
  const [bars, setBars] = useState<Bar[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchBars = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `/.netlify/functions/alpaca-bars?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`
      )
      if (!res.ok) throw new Error(`Failed to fetch bars: ${res.status}`)
      const data = await res.json() as { bars?: Array<{ t: string; o: number; h: number; l: number; c: number; v: number }> }
      const mapped: Bar[] = (data.bars || []).map((b) => ({
        time: Math.floor(new Date(b.t).getTime() / 1000),
        open: b.o,
        high: b.h,
        low: b.l,
        close: b.c,
        volume: b.v,
      }))
      setBars(mapped)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [symbol, timeframe, limit])

  useEffect(() => {
    void fetchBars()
    const timer = setInterval(fetchBars, 60000)
    return () => clearInterval(timer)
  }, [fetchBars])

  return { bars, loading, error, refetch: fetchBars }
}
