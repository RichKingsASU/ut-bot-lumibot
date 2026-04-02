import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../lib/supabaseClient'

export interface RiskConfig {
  id: string
  mode: 'paper' | 'live'
  max_position_pct: number
  max_daily_loss: number
  max_drawdown_pct: number
  max_positions: number
  per_trade_risk_pct: number
  stop_loss_pct: number
  take_profit_pct: number
  trailing_stop: boolean
  trailing_stop_pct: number
  kelly_fraction: number
  use_kelly: boolean
  cooldown_minutes: number
  updated_at: string
}

const DEFAULT_RISK_CONFIG: RiskConfig = {
  id: '1',
  mode: 'paper',
  max_position_pct: 5,
  max_daily_loss: 500,
  max_drawdown_pct: 10,
  max_positions: 3,
  per_trade_risk_pct: 1,
  stop_loss_pct: 2,
  take_profit_pct: 4,
  trailing_stop: true,
  trailing_stop_pct: 1.5,
  kelly_fraction: 0.25,
  use_kelly: false,
  cooldown_minutes: 5,
  updated_at: new Date().toISOString(),
}

interface UseRiskConfigResult {
  config: RiskConfig
  loading: boolean
  error: string | null
  updateConfig: (updates: Partial<RiskConfig>) => Promise<void>
  resetToDefaults: () => void
}

export function useRiskConfig(): UseRiskConfigResult {
  const [config, setConfig] = useState<RiskConfig>(DEFAULT_RISK_CONFIG)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data, error: dbError } = await supabase
        .from('risk_config')
        .select('*')
        .eq('id', '1')
        .single()
      if (dbError) {
        if (dbError.code === 'PGRST116') {
          setConfig(DEFAULT_RISK_CONFIG)
        } else {
          throw dbError
        }
      } else if (data) {
        setConfig(data as RiskConfig)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchConfig()
  }, [fetchConfig])

  const updateConfig = useCallback(async (updates: Partial<RiskConfig>) => {
    const updated = { ...config, ...updates, updated_at: new Date().toISOString() }
    setConfig(updated)
    try {
      const { error: dbError } = await supabase
        .from('risk_config')
        .upsert([updated])
      if (dbError) throw dbError
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      await fetchConfig()
    }
  }, [config, fetchConfig])

  const resetToDefaults = useCallback(() => {
    setConfig(DEFAULT_RISK_CONFIG)
  }, [])

  return { config, loading, error, updateConfig, resetToDefaults }
}
