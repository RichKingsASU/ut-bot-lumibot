import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react'
import { useAlpacaAccount } from '../hooks/useAlpacaAccount'
import { useAlpacaStream } from '../hooks/useAlpacaStream'
import { useUTBot } from '../hooks/useUTBot'
import { useBotStatus, type BotStatusData } from '../hooks/useBotStatus'
import type { Timeframe, LogEntry, OHLCV, Signal } from '../types/dashboard'
import type { AlpacaAccount, AlpacaPosition, AlpacaOrder } from '../types/alpaca'

const DEFAULT_SYMBOL = import.meta.env.VITE_DEFAULT_SYMBOL || 'IWM'
const DEFAULT_TIMEFRAME = (import.meta.env.VITE_DEFAULT_TIMEFRAME || '15m') as Timeframe

interface TradingContextValue {
  symbol: string
  setSymbol: (s: string) => void
  timeframe: Timeframe
  setTimeframe: (tf: Timeframe) => void
  
  account: AlpacaAccount | null
  accountUpdatedAt: Date | null
  positions: AlpacaPosition[]
  orders: AlpacaOrder[]
  isInTrade: boolean
  activePosition: AlpacaPosition | null
  loading: boolean
  error: string | null

  candles: OHLCV[]
  currentPrice: number | null
  connected: boolean
  prevClose: number | null

  trailStops: (number | null)[]
  signals: Signal[]
  currentTrailStop: number | null
  currentATR: number | null
  lastSignal: Signal | null

  logs: LogEntry[]
  addLog: (message: string, level?: LogEntry['level']) => void
  iterationsToday: number
  botStatus: BotStatusData
}

const TradingContext = createContext<TradingContextValue | undefined>(undefined)

export function TradingProvider({ children }: { children: ReactNode }) {
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL)
  const [timeframe, setTimeframe] = useState<Timeframe>(DEFAULT_TIMEFRAME)
  const [iterationsToday] = useState(0)

  const [logs, setLogs] = useState<LogEntry[]>([
    { id: '1', timestamp: new Date(), message: 'Dashboard initialized — connecting to Alpaca Markets', level: 'info' },
  ])

  const addLog = useCallback((message: string, level: LogEntry['level'] = 'info') => {
    setLogs((prev) => [
      ...prev.slice(-49),
      { id: String(Date.now()), timestamp: new Date(), message, level },
    ])
  }, [])

  const { account, accountUpdatedAt, positions, orders, isInTrade, activePosition, loading, error } = useAlpacaAccount(symbol)
  const { candles, currentPrice, connected, prevClose } = useAlpacaStream(symbol, timeframe)
  const botStatus = useBotStatus()
  const { trailStops, signals, currentTrailStop, currentATR, lastSignal } = useUTBot(candles, {
    atrPeriod: 10,
    sensitivity: 1.0,
  })

  // Track connect/disconnect transitions and log them as alerts (F-5)
  const prevConnectedRef = useRef<boolean | null>(null)
  const latestConnectedRef = useRef(connected)
  useEffect(() => { latestConnectedRef.current = connected }, [connected])

  useEffect(() => {
    if (prevConnectedRef.current === null) {
      prevConnectedRef.current = connected
      return
    }
    if (prevConnectedRef.current === connected) return
    if (!connected) {
      addLog('🔴 Alpaca Markets disconnected', 'error')
    } else {
      addLog('Alpaca Markets reconnected', 'info')
    }
    prevConnectedRef.current = connected
  }, [connected, addLog])

  // After 10 s on page load, if still not connected, show failure banner in alerts (F-5)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!latestConnectedRef.current) {
        addLog('⚠ Alpaca Markets connection failed — broker offline or key not set', 'error')
      }
    }, 10_000)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSymbolChange = (s: string) => {
    setSymbol(s)
    addLog(`Symbol changed to ${s}`, 'info')
  }

  const handleTimeframeChange = (tf: Timeframe) => {
    setTimeframe(tf)
    addLog(`Timeframe changed to ${tf}`, 'info')
  }

  const value: TradingContextValue = {
    symbol,
    setSymbol: handleSymbolChange,
    timeframe,
    setTimeframe: handleTimeframeChange,
    
    account,
    accountUpdatedAt,
    positions,
    orders,
    isInTrade,
    activePosition,
    loading,
    error,
    
    candles,
    currentPrice,
    connected,
    prevClose,
    
    trailStops,
    signals,
    currentTrailStop,
    currentATR,
    lastSignal,
    
    logs,
    addLog,
    iterationsToday,
    botStatus,
  }

  return <TradingContext.Provider value={value}>{children}</TradingContext.Provider>
}

export function useTradingContext() {
  const context = useContext(TradingContext)
  if (context === undefined) {
    throw new Error('useTradingContext must be used within a TradingProvider')
  }
  return context
}
