import React, { useState, useCallback } from 'react'
import { TopBar } from './components/TopBar'
import { OHLCBar } from './components/OHLCBar'
import { InTradeBar } from './components/InTradeBar'
import { CandlestickChart } from './components/CandlestickChart'
import { VolumeChart } from './components/VolumeChart'
import { IndicatorToolbar } from './components/IndicatorToolbar'
import { BottomLogBar } from './components/BottomLogBar'
import { AccountOverview } from './components/SidePanel/AccountOverview'
import { ActiveTrade } from './components/SidePanel/ActiveTrade'
import { Positions } from './components/SidePanel/Positions'
import { OrderPanel } from './components/SidePanel/OrderPanel'
import { BotStatus } from './components/SidePanel/BotStatus'
import { useAlpacaAccount } from './hooks/useAlpacaAccount'
import { useAlpacaStream } from './hooks/useAlpacaStream'
import { useUTBot } from './hooks/useUTBot'
import { LoginPage } from './components/LoginPage'
import SeedStatus from './components/SeedStatus'
import { supabase } from './lib/supabaseClient'
import type { IndicatorState, Timeframe, OHLCV, LogEntry } from './types/dashboard'
import type { Session } from '@supabase/supabase-js'


const DEFAULT_SYMBOL = import.meta.env.VITE_DEFAULT_SYMBOL || 'IWM'
const DEFAULT_TIMEFRAME = (import.meta.env.VITE_DEFAULT_TIMEFRAME || '15m') as Timeframe

const DEFAULT_INDICATORS: IndicatorState = {
  atrStop: true,
  signals: true,
  volume: true,
  srLines: true,
  ema9: false,
  ema21: false,
  vwap: false,
  rsi: false,
  macd: false,
  bollinger: false,
}

function useLogs() {
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: '1', timestamp: new Date(), message: 'Dashboard initialized — connecting to Alpaca Markets', level: 'info' },
  ])

  const addLog = useCallback((message: string, level: LogEntry['level'] = 'info') => {
    setLogs((prev) => [
      ...prev.slice(-49),
      { id: String(Date.now()), timestamp: new Date(), message, level },
    ])
  }, [])

  return { logs, addLog }
}

type SidePanelTab = 'account' | 'trade' | 'positions' | 'orders' | 'bot' | 'data'

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL)
  const [timeframe, setTimeframe] = useState<Timeframe>(DEFAULT_TIMEFRAME)
  const [indicators, setIndicators] = useState<IndicatorState>(DEFAULT_INDICATORS)
  const [hoveredCandle, setHoveredCandle] = useState<OHLCV | null>(null)
  const [sideTab, setSideTab] = useState<SidePanelTab>('account')
  const [iterationsToday] = useState(0)

  React.useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setAuthLoading(false)
    })

    // Listen for changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })

    return () => subscription.unsubscribe()
  }, [])

  const { logs, addLog } = useLogs()

  const { account, positions, orders, isInTrade, activePosition, loading, error } = useAlpacaAccount(symbol)
  const { candles, currentPrice, connected, prevClose } = useAlpacaStream(symbol, timeframe)
  const { trailStops, signals, currentTrailStop, currentATR, lastSignal } = useUTBot(candles, {
    atrPeriod: 10,
    sensitivity: 1.0,
  })

  const handleIndicatorToggle = (key: keyof IndicatorState) => {
    setIndicators((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSymbolChange = (s: string) => {
    setSymbol(s)
    addLog(`Symbol changed to ${s}`, 'info')
  }

  const handleTimeframeChange = (tf: Timeframe) => {
    setTimeframe(tf)
    addLog(`Timeframe changed to ${tf}`, 'info')
  }

  const lastCandle = candles.length > 0 ? candles[candles.length - 1] : null
  const activeEntryTime = activePosition ? (activePosition as { updated_at?: string }).updated_at ?? '' : undefined

  const SIDE_TABS: Array<{ key: SidePanelTab; label: string }> = [
    { key: 'account', label: 'Account' },
    { key: 'trade', label: 'Trade' },
    { key: 'positions', label: 'Positions' },
    { key: 'orders', label: 'Orders' },
    { key: 'bot', label: 'Bot' },
    { key: 'data', label: 'Data' },
  ]

  if (authLoading) {
    return (
      <div style={{ 
        height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', 
        background: 'var(--bg-primary)', color: 'var(--text-muted)' 
      }}>
        Initializing...
      </div>
    )
  }

  if (!session) {
    return <LoginPage />
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg-primary)' }}>


      {/* TOP BAR */}
      <TopBar
        symbol={symbol}
        timeframe={timeframe}
        currentPrice={currentPrice}
        prevClose={prevClose}
        isInTrade={isInTrade}
        tradeSide={activePosition?.side ?? null}
        botRunning={connected}
        connected={connected}
        onSymbolChange={handleSymbolChange}
        onTimeframeChange={handleTimeframeChange}
      />

      {/* IN TRADE BAR */}
      <InTradeBar
        isInTrade={isInTrade}
        position={activePosition}
        currentPrice={currentPrice}
        trailStop={currentTrailStop}
        entryTime={activeEntryTime}
      />

      {/* MAIN CONTENT */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* CHART AREA */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* OHLC Data Bar */}
          <OHLCBar candle={lastCandle} hoveredCandle={hoveredCandle} />

          {/* Indicator Toolbar */}
          <IndicatorToolbar indicators={indicators} onChange={handleIndicatorToggle} />

          {/* Chart */}
          <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
            <CandlestickChart
              candles={candles}
              trailStops={trailStops}
              signals={signals}
              indicators={indicators}
              currentPrice={currentPrice}
              entryPrice={activePosition ? parseFloat(activePosition.avg_entry_price) : undefined}
              onCrosshairMove={setHoveredCandle}
            />
          </div>

          {/* Volume Chart */}
          <VolumeChart candles={candles} visible={indicators.volume} />
        </div>

        {/* SIDE PANEL */}
        <div style={{
          width: '280px',
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          borderLeft: '1px solid var(--border)',
          background: 'var(--bg-secondary)',
          overflow: 'hidden',
        }}>
          {/* Side Panel Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
            {SIDE_TABS.map(({ key, label }) => (
              <button
                key={key}
                id={`side-tab-${key}`}
                onClick={() => setSideTab(key)}
                style={{
                  flex: 1, padding: '8px 2px', border: 'none', cursor: 'pointer',
                  background: sideTab === key ? 'var(--bg-tertiary)' : 'transparent',
                  color: sideTab === key ? 'var(--text-primary)' : 'var(--text-muted)',
                  fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
                  borderBottom: sideTab === key ? '2px solid var(--blue)' : '2px solid transparent',
                  letterSpacing: '0.04em',
                }}
              >{label}</button>
            ))}
          </div>

          {/* Side Panel Content */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            {sideTab === 'account' && <AccountOverview account={account} loading={loading} />}
            {sideTab === 'trade' && (
              <ActiveTrade
                position={activePosition}
                currentPrice={currentPrice}
                trailStop={currentTrailStop}
                lastSignal={lastSignal?.type ?? ''}
              />
            )}
            {sideTab === 'positions' && <Positions positions={positions} />}
            {sideTab === 'orders' && <OrderPanel orders={orders} />}
            {sideTab === 'bot' && (
              <BotStatus
                symbol={symbol}
                timeframe={timeframe}
                atrPeriod={10}
                sensitivity={1.0}
                currentATR={currentATR}
                currentTrailStop={currentTrailStop}
                lastSignal={lastSignal?.type ?? ''}
                iterationsToday={iterationsToday}
                connected={connected}
              />
            )}
            {sideTab === 'data' && <SeedStatus />}
          </div>
        </div>
      </div>

      {/* BOTTOM LOG BAR */}
      <BottomLogBar logs={logs} connected={connected} />
    </div>
  )
}
