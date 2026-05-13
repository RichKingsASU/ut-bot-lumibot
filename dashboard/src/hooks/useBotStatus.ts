import { useState, useEffect, useRef, useCallback } from 'react'

export interface BotStatusData {
  online: boolean
  status: 'online' | 'offline' | 'stale' | 'error' | 'connecting'
  last_heartbeat: string | null
  session_id: string | null
  symbol: string | null
  mode: string | null
  uptime_seconds: number | null
  last_signal: string | null
  last_signal_time: string | null
  seconds_since_heartbeat: number | null
}

const POLL_INTERVAL = 10_000 // 10 seconds
const ENDPOINT = '/.netlify/functions/bot-status'

const DEFAULT_STATUS: BotStatusData = {
  online: false,
  status: 'connecting',
  last_heartbeat: null,
  session_id: null,
  symbol: null,
  mode: null,
  uptime_seconds: null,
  last_signal: null,
  last_signal_time: null,
  seconds_since_heartbeat: null,
}

export function useBotStatus(): BotStatusData {
  const [data, setData] = useState<BotStatusData>(DEFAULT_STATUS)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const adminKey = import.meta.env.VITE_ADMIN_API_KEY || '';
      const res = await fetch(ENDPOINT, {
        headers: {
          'X-Admin-API-Key': adminKey
        }
      })
      if (!res.ok) {
        setData(prev => ({ ...prev, online: false, status: 'error' }))
        return
      }
      const json = await res.json()
      setData(json)
    } catch {
      setData(prev => ({ ...prev, online: false, status: 'connecting' }))
    }
  }, [])

  useEffect(() => {
    // Fetch immediately on mount
    fetchStatus()

    // Then poll every 10s
    intervalRef.current = setInterval(fetchStatus, POLL_INTERVAL)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchStatus])

  return data
}
