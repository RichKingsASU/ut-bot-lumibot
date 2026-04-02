import { useState, useEffect, useCallback } from 'react'
import { supabase } from '../lib/supabaseClient'
import type { Strategy } from '../types/strategy'

interface UseStrategiesResult {
  strategies: Strategy[]
  loading: boolean
  error: string | null
  createStrategy: (strategy: Omit<Strategy, 'id' | 'created_at' | 'updated_at'>) => Promise<void>
  updateStrategy: (id: string, updates: Partial<Strategy>) => Promise<void>
  deleteStrategy: (id: string) => Promise<void>
  refetch: () => void
}

export function useStrategies(): UseStrategiesResult {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStrategies = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data, error: dbError } = await supabase
        .from('strategies')
        .select('*')
        .order('created_at', { ascending: false })
      if (dbError) throw dbError
      setStrategies((data as Strategy[]) || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchStrategies()
  }, [fetchStrategies])

  const createStrategy = useCallback(async (strategy: Omit<Strategy, 'id' | 'created_at' | 'updated_at'>) => {
    const { error: dbError } = await supabase.from('strategies').insert([strategy])
    if (dbError) throw dbError
    await fetchStrategies()
  }, [fetchStrategies])

  const updateStrategy = useCallback(async (id: string, updates: Partial<Strategy>) => {
    const { error: dbError } = await supabase.from('strategies').update(updates).eq('id', id)
    if (dbError) throw dbError
    await fetchStrategies()
  }, [fetchStrategies])

  const deleteStrategy = useCallback(async (id: string) => {
    const { error: dbError } = await supabase.from('strategies').delete().eq('id', id)
    if (dbError) throw dbError
    await fetchStrategies()
  }, [fetchStrategies])

  return { strategies, loading, error, createStrategy, updateStrategy, deleteStrategy, refetch: fetchStrategies }
}
