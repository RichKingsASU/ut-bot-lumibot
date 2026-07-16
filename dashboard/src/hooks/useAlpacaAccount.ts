import { useState, useEffect, useCallback, useRef } from 'react'
import type { AlpacaAccount, AlpacaPosition, AlpacaOrder } from '../types/alpaca'
import { netlifyFetch } from '../lib/apiClient'

interface AlpacaAccountState {
  account: AlpacaAccount | null
  positions: AlpacaPosition[]
  orders: AlpacaOrder[]
  isInTrade: boolean
  activePosition: AlpacaPosition | null
  loading: boolean
  error: string | null
  accountUpdatedAt: Date | null
}

const ACCOUNT_INTERVAL = 60000
const POSITIONS_INTERVAL = 5000
const ORDERS_INTERVAL = 10000
const MAX_AUTH_FAILURES = 3

export function useAlpacaAccount(symbol: string): AlpacaAccountState {
  const [account, setAccount] = useState<AlpacaAccount | null>(null)
  const [positions, setPositions] = useState<AlpacaPosition[]>([])
  const [orders, setOrders] = useState<AlpacaOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [accountUpdatedAt, setAccountUpdatedAt] = useState<Date | null>(null)
  const authFailures = useRef(0)
  const stoppedRef = useRef(false)

  const fetchAccount = useCallback(async () => {
    if (stoppedRef.current) return
    try {
      const res = await netlifyFetch('alpaca-account')
      if (res.status === 401) {
        authFailures.current += 1
        if (authFailures.current >= MAX_AUTH_FAILURES) stoppedRef.current = true
        setError('Unauthorized — set Admin API Key in Settings.')
        return
      }
      if (!res.ok) throw new Error(`Account fetch failed: ${res.status}`)
      authFailures.current = 0
      const data = await res.json()
      setAccount(data)
      setAccountUpdatedAt(new Date())
    } catch (e) {
      setError(String(e))
    }
  }, [])

  const fetchPositions = useCallback(async () => {
    if (stoppedRef.current) return
    try {
      const res = await netlifyFetch('alpaca-positions')
      if (res.status === 401) return
      if (!res.ok) throw new Error(`Positions fetch failed: ${res.status}`)
      const data = await res.json()
      setPositions(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(String(e))
    }
  }, [])

  const fetchOrders = useCallback(async () => {
    if (stoppedRef.current) return
    try {
      const res = await netlifyFetch('alpaca-orders')
      if (res.status === 401) return
      if (!res.ok) throw new Error(`Orders fetch failed: ${res.status}`)
      const data = await res.json()
      setOrders(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(String(e))
    }
  }, [])

  useEffect(() => {
    stoppedRef.current = false
    authFailures.current = 0
    const init = async () => {
      setLoading(true)
      await Promise.all([fetchAccount(), fetchPositions(), fetchOrders()])
      setLoading(false)
    }
    void init()

    const accountTimer = setInterval(fetchAccount, ACCOUNT_INTERVAL)
    const positionsTimer = setInterval(fetchPositions, POSITIONS_INTERVAL)
    const ordersTimer = setInterval(fetchOrders, ORDERS_INTERVAL)

    return () => {
      clearInterval(accountTimer)
      clearInterval(positionsTimer)
      clearInterval(ordersTimer)
    }
  }, [fetchAccount, fetchPositions, fetchOrders])

  const activePosition = positions.find(
    (p) => p.symbol.toUpperCase() === symbol.toUpperCase()
  ) ?? null

  return {
    account,
    positions,
    orders,
    isInTrade: activePosition !== null,
    activePosition,
    loading,
    error,
    accountUpdatedAt,
  }
}
