import { useState, useEffect, useCallback, useRef } from 'react'
import type { AlpacaAccount, AlpacaPosition, AlpacaOrder } from '../types/alpaca'

interface AlpacaAccountState {
  account: AlpacaAccount | null
  positions: AlpacaPosition[]
  orders: AlpacaOrder[]
  isInTrade: boolean
  activePosition: AlpacaPosition | null
  loading: boolean
  error: string | null
}

const ACCOUNT_INTERVAL = 15000
const POSITIONS_INTERVAL = 5000
const ORDERS_INTERVAL = 10000

export function useAlpacaAccount(symbol: string): AlpacaAccountState {
  const [account, setAccount] = useState<AlpacaAccount | null>(null)
  const [positions, setPositions] = useState<AlpacaPosition[]>([])
  const [orders, setOrders] = useState<AlpacaOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAccount = useCallback(async () => {
    try {
      const res = await fetch('/.netlify/functions/alpaca-account')
      if (!res.ok) throw new Error(`Account fetch failed: ${res.status}`)
      const data = await res.json()
      setAccount(data)
    } catch (e) {
      setError(String(e))
    }
  }, [])

  const fetchPositions = useCallback(async () => {
    try {
      const res = await fetch('/.netlify/functions/alpaca-positions')
      if (!res.ok) throw new Error(`Positions fetch failed: ${res.status}`)
      const data = await res.json()
      setPositions(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(String(e))
    }
  }, [])

  const fetchOrders = useCallback(async () => {
    try {
      const res = await fetch('/.netlify/functions/alpaca-orders')
      if (!res.ok) throw new Error(`Orders fetch failed: ${res.status}`)
      const data = await res.json()
      setOrders(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(String(e))
    }
  }, [])

  useEffect(() => {
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
  }
}
