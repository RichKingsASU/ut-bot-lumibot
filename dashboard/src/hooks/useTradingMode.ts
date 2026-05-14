import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabaseClient'

export type TradingMode = 'paper' | 'live' | 'unknown'

function parsePaperMode(value: unknown): boolean | null {
  if (value === null || value === undefined) return null
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (trimmed === 'true') return true
    if (trimmed === 'false') return false
    try {
      const parsed = JSON.parse(trimmed)
      if (typeof parsed === 'boolean') return parsed
      if (parsed && typeof parsed === 'object' && 'paper_mode' in parsed) {
        return Boolean((parsed as { paper_mode: unknown }).paper_mode)
      }
    } catch {
      return null
    }
  }
  if (typeof value === 'object' && value !== null && 'paper_mode' in value) {
    return Boolean((value as { paper_mode: unknown }).paper_mode)
  }
  return null
}

export function useTradingMode(): TradingMode {
  const [mode, setMode] = useState<TradingMode>('unknown')

  useEffect(() => {
    let cancelled = false
    async function fetchMode() {
      const { data } = await supabase
        .from('user_settings')
        .select('value')
        .eq('key', 'paper_mode')
        .maybeSingle()
      if (cancelled) return
      const paper = parsePaperMode(data?.value)
      if (paper === null) setMode('unknown')
      else setMode(paper ? 'paper' : 'live')
    }
    fetchMode()
    return () => {
      cancelled = true
    }
  }, [])

  return mode
}

export interface TradingModeBadgeStyle {
  background: string
  color: string
  border: string
  label: string
}

export function tradingModeBadgeStyle(mode: TradingMode): TradingModeBadgeStyle {
  if (mode === 'paper') {
    return {
      background: 'rgba(63,185,80,0.2)',
      color: '#3fb950',
      border: '1px solid #3fb950',
      label: 'PAPER',
    }
  }
  if (mode === 'live') {
    return {
      background: 'rgba(248,81,73,0.25)',
      color: '#f85149',
      border: '1px solid #f85149',
      label: 'LIVE',
    }
  }
  return {
    background: 'rgba(139,148,158,0.2)',
    color: '#8b949e',
    border: '1px solid #8b949e',
    label: '...',
  }
}
