import { useState, useEffect, useRef, useCallback } from 'react'
import { netlifyFetch } from '../lib/apiClient'

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

const POLL_INTERVAL = 10_000
const MAX_AUTH_FAILURES = 3

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
  const authFailures = useRef(0)
  const stoppedRef = useRef(false)

  const fetchStatus = useCallback(async () => {
    if (stoppedRef.current) return
    try {
      const res = await netlifyFetch('bot-status')
      if (res.status === 401) {
        authFailures.current += 1
        if (authFailures.current >= MAX_AUTH_FAILURES) {
          stoppedRef.current = true
          if (intervalRef.current) clearInterval(intervalRef.current)
        }
        setData(prev => ({ ...prev, online: false, status: 'error' }))
        return
      }
      if (!res.ok) {
        setData(prev => ({ ...prev, online: false, status: 'error' }))
        return
      }
      authFailures.current = 0
      const json = await res.json()
      setData(json)
    } catch {
      setData(prev => ({ ...prev, online: false, status: 'connecting' }))
    }
  }, [])

  useEffect(() => {
    stoppedRef.current = false
    authFailures.current = 0
    fetchStatus()
    intervalRef.current = setInterval(fetchStatus, POLL_INTERVAL)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchStatus])

  return data
}
