import { useState, useEffect, useRef, useCallback } from 'react'
import { supabase } from '../lib/supabaseClient'

/**
 * Subscribes to Supabase Realtime channels for bot_status, agent_signals,
 * and system_alerts tables. Returns the latest payloads and a heartbeat
 * latency measurement.
 *
 * This replaces polling for these tables with push-based updates.
 */

export interface RealtimeState {
  /** Latest bot_status row from realtime INSERT/UPDATE */
  latestBotStatus: Record<string, any> | null
  /** Latest agent_signal row from realtime INSERT */
  latestSignal: Record<string, any> | null
  /** Latest system_alert row from realtime INSERT */
  latestAlert: Record<string, any> | null
  /** Whether the realtime channel is connected */
  realtimeConnected: boolean
  /** Milliseconds since last realtime message was received */
  heartbeatAgeMs: number | null
}

export function useSupabaseRealtime(): RealtimeState {
  const [latestBotStatus, setLatestBotStatus] = useState<Record<string, any> | null>(null)
  const [latestSignal, setLatestSignal] = useState<Record<string, any> | null>(null)
  const [latestAlert, setLatestAlert] = useState<Record<string, any> | null>(null)
  const [realtimeConnected, setRealtimeConnected] = useState(false)
  const [heartbeatAgeMs, setHeartbeatAgeMs] = useState<number | null>(null)
  const lastMessageAt = useRef<number | null>(null)

  // Update heartbeatAgeMs every second
  useEffect(() => {
    const timer = setInterval(() => {
      if (lastMessageAt.current) {
        setHeartbeatAgeMs(Date.now() - lastMessageAt.current)
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const channel = supabase
      .channel('operator-console')
      .on(
        'postgres_changes' as any,
        { event: '*', schema: 'public', table: 'bot_status' },
        (payload: any) => {
          lastMessageAt.current = Date.now()
          setLatestBotStatus(payload.new || payload)
        }
      )
      .on(
        'postgres_changes' as any,
        { event: 'INSERT', schema: 'public', table: 'agent_signals' },
        (payload: any) => {
          lastMessageAt.current = Date.now()
          setLatestSignal(payload.new || payload)
        }
      )
      .on(
        'postgres_changes' as any,
        { event: 'INSERT', schema: 'public', table: 'system_alerts' },
        (payload: any) => {
          lastMessageAt.current = Date.now()
          setLatestAlert(payload.new || payload)
        }
      )
      .subscribe((status: string) => {
        setRealtimeConnected(status === 'SUBSCRIBED')
      })

    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  return {
    latestBotStatus,
    latestSignal,
    latestAlert,
    realtimeConnected,
    heartbeatAgeMs,
  }
}
