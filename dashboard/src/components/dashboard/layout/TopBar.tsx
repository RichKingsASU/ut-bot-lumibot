import React, { useState, useEffect, useMemo, useRef } from 'react'
import { useTradingContext } from '../../../context/TradingContext'
import { fmtPrice } from '../../../utils/formatters'
import { supabase } from '../../../lib/supabaseClient'
import { useTradingMode, tradingModeBadgeStyle } from '../../../hooks/useTradingMode'

type Timeframe = '1m' | '5m' | '15m' | '1h' | '1D'
const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '1D']

function getMarketSession(): { label: string; color: string } {
  const now = new Date()
  // Convert to ET
  const et = new Date(
    now.toLocaleString('en-US', { timeZone: 'America/New_York' })
  )
  const hours = et.getHours()
  const minutes = et.getMinutes()
  const totalMinutes = hours * 60 + minutes

  if (totalMinutes >= 240 && totalMinutes < 570) {
    return { label: 'PRE-MARKET', color: '#e3b341' }
  }
  if (totalMinutes >= 570 && totalMinutes < 960) {
    return { label: 'MARKET OPEN', color: '#3fb950' }
  }
  if (totalMinutes >= 960 && totalMinutes < 1200) {
    return { label: 'AFTER-HOURS', color: '#e3b341' }
  }
  return { label: 'CLOSED', color: '#8b949e' }
}

export function TopBar() {
  const {
    symbol,
    setSymbol,
    timeframe,
    setTimeframe,
    currentPrice,
    prevClose,
    account,
    accountUpdatedAt,
    botStatus,
    connected,
  } = useTradingContext()

  const [editingSymbol, setEditingSymbol] = useState(false)
  const [symbolInput, setSymbolInput] = useState(symbol)
  const [marketSession, setMarketSession] = useState(getMarketSession)
  const inputRef = useRef<HTMLInputElement>(null)

  // Refresh market session every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setMarketSession(getMarketSession())
    }, 30_000)
    return () => clearInterval(interval)
  }, [])

  // Focus input when editing
  useEffect(() => {
    if (editingSymbol && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editingSymbol])

  const handleSymbolSubmit = () => {
    const trimmed = symbolInput.trim().toUpperCase()
    if (trimmed) {
      setSymbol(trimmed)
    } else {
      setSymbolInput(symbol)
    }
    setEditingSymbol(false)
  }

  // Price change
  const priceUp =
    currentPrice != null && prevClose != null ? currentPrice >= prevClose : true
  const priceColor = priceUp ? '#3fb950' : '#f85149'

  // Header P&L is a stable snapshot — it only recomputes when the account
  // payload from useAlpacaAccount actually changes (every 60s), so the
  // displayed value doesn't fluctuate as the user navigates between pages.
  const pnl = useMemo<number | null>(() => {
    if (!account) return null
    const equity = parseFloat(account.equity)
    const lastEquity = parseFloat(account.last_equity)
    if (isNaN(equity) || isNaN(lastEquity)) return null
    return equity - lastEquity
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountUpdatedAt])

  const updatedAgo = (() => {
    if (!accountUpdatedAt) return ''
    const secs = Math.max(0, Math.round((Date.now() - accountUpdatedAt.getTime()) / 1000))
    if (secs < 60) return `${secs}s ago`
    return `${Math.floor(secs / 60)}m ago`
  })()

  const botRunning = botStatus?.status === 'online'
  const online = connected
  const tradingMode = useTradingMode()
  const modeBadge = tradingModeBadgeStyle(tradingMode)

  return (
    <header
      className="flex items-center justify-between gap-4 h-16 px-6 bg-surface-1/40 border-b border-border-muted/50 backdrop-blur-md flex-shrink-0 z-40 relative"
    >
      {/* Left side: Symbol Selection & Price */}
      <div className="flex items-center gap-4">
        {editingSymbol ? (
          <input
            ref={inputRef}
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            onBlur={handleSymbolSubmit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSymbolSubmit()
              if (e.key === 'Escape') {
                setSymbolInput(symbol)
                setEditingSymbol(false)
              }
            }}
            className="bg-surface-2 border border-blue-500 rounded-lg text-primary text-sm font-semibold px-3 py-1.5 w-24 outline-none transition-smooth"
          />
        ) : (
          <button
            onClick={() => {
              setSymbolInput(symbol)
              setEditingSymbol(true)
            }}
            className="px-3.5 py-1.5 bg-surface-2/65 hover:bg-surface-3 border border-border-muted hover:border-vibrant rounded-xl text-primary text-sm font-semibold transition-smooth cursor-pointer shadow-sm flex items-center gap-1.5"
          >
            <span className="text-[10px] text-dim font-bold uppercase tracking-wider">Asset:</span>
            {symbol}
          </button>
        )}

        {currentPrice != null && (
          <div className="flex flex-col">
            <span style={{ color: priceColor }} className="font-bold text-base leading-none transition-smooth">
              {fmtPrice(currentPrice)}
            </span>
            {prevClose != null && (
              <span className="text-[9px] text-dim font-bold tracking-tight mt-0.5">
                {priceUp ? '▲' : '▼'} {(((currentPrice - prevClose) / prevClose) * 100).toFixed(2)}%
              </span>
            )}
          </div>
        )}

        <div className="w-px h-6 bg-border-muted/50 hidden sm:block" />

        {/* Timeframe selector */}
        <div className="hidden sm:flex gap-1 bg-surface-2/40 p-1 border border-border-muted/50 rounded-xl">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-smooth cursor-pointer ${
                timeframe === tf
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-secondary hover:text-vibrant'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>

        {pnl !== null && (
          <>
            <div className="w-px h-6 bg-border-muted/50 hidden md:block" />
            <div 
              title={accountUpdatedAt ? `Last updated ${updatedAgo}` : undefined}
              className="hidden md:flex flex-col cursor-help"
            >
              <span className="text-[9px] text-dim font-bold uppercase tracking-wider">Session P&L</span>
              <span className={`text-xs font-bold mt-0.5 ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {pnl >= 0 ? '+' : ''}{fmtPrice(pnl)}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Right side: Session State, Active Mode, Connection, Sign out */}
      <div className="flex items-center gap-4">
        {/* Session Status */}
        <span
          className="text-[9px] font-bold px-2.5 py-1 rounded-lg border flex items-center gap-1.5 transition-smooth"
          style={{
            background: `${marketSession.color}12`,
            color: marketSession.color,
            borderColor: `${marketSession.color}33`,
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: marketSession.color }} />
          {marketSession.label}
        </span>

        {/* Bot active indicator */}
        <span
          className={`text-[9px] font-bold px-2.5 py-1 rounded-lg border flex items-center gap-1.5 transition-smooth ${
            botRunning 
              ? 'bg-green-500/10 text-green-400 border-green-500/30' 
              : 'bg-red-500/10 text-red-400 border-red-500/30'
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${botRunning ? 'bg-green-400' : 'bg-red-400'} ${botRunning ? 'animate-pulse' : ''}`} />
          {botRunning ? 'BOT ACTIVE' : 'BOT OFFLINE'}
        </span>

        {/* Mode badge */}
        <span
          className="text-[9px] font-bold px-2.5 py-1 rounded-lg border transition-smooth"
          style={{
            background: modeBadge.background,
            color: modeBadge.color,
            border: modeBadge.border,
          }}
        >
          {modeBadge.label}
        </span>

        {/* Online state */}
        <div
          className={`flex items-center gap-1.5 text-[10px] font-semibold cursor-help ${
            online ? 'text-green-400' : 'text-red-400'
          }`}
          title={online ? 'CONNECTED TO ALPACA API' : 'DISCONNECTED FROM ALPACA API'}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-green-400' : 'bg-red-400'} ${online ? 'animate-ping' : ''}`} />
          {online ? 'ONLINE' : 'OFFLINE'}
        </div>

        <div className="w-px h-6 bg-border-muted/50" />

        {/* Logout */}
        <button
          onClick={() => supabase.auth.signOut()}
          aria-label="Sign out"
          title="Sign out"
          className="p-2 hover:bg-surface-2 rounded-xl text-dim hover:text-red-400 transition-smooth cursor-pointer"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </header>
  )
}
