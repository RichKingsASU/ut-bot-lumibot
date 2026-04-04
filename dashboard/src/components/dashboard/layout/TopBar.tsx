import React, { useState, useEffect, useRef } from 'react'
import { useTradingContext } from '../../../context/TradingContext'
import { fmtPrice } from '../../../utils/formatters'
import { supabase } from '../../../lib/supabaseClient'

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

  // P&L
  let pnl: number | null = null
  if (account) {
    const equity = parseFloat(account.equity)
    const lastEquity = parseFloat(account.last_equity)
    if (!isNaN(equity) && !isNaN(lastEquity)) {
      pnl = equity - lastEquity
    }
  }

  const botRunning = botStatus?.status === 'online'
  const online = connected

  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        height: 48,
        padding: '0 16px',
        background: '#161b22',
        borderBottom: '1px solid #30363d',
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <span
        style={{
          fontWeight: 700,
          fontSize: 14,
          color: '#58a6ff',
          whiteSpace: 'nowrap',
          letterSpacing: 1,
        }}
      >
        ◆ DISRUPTING ALPHA
      </span>

      <div style={{ width: 1, height: 24, background: '#30363d' }} />

      {/* Symbol pill */}
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
          style={{
            background: '#21262d',
            border: '1px solid #58a6ff',
            borderRadius: 4,
            color: '#e6edf3',
            fontSize: 13,
            fontWeight: 600,
            padding: '3px 8px',
            width: 80,
            outline: 'none',
          }}
        />
      ) : (
        <button
          onClick={() => {
            setSymbolInput(symbol)
            setEditingSymbol(true)
          }}
          style={{
            background: '#21262d',
            border: '1px solid #30363d',
            borderRadius: 4,
            color: '#e6edf3',
            fontSize: 13,
            fontWeight: 600,
            padding: '3px 10px',
            cursor: 'pointer',
          }}
        >
          {symbol}
        </button>
      )}

      {/* Current price */}
      {currentPrice != null && (
        <span style={{ color: priceColor, fontWeight: 600, fontSize: 14 }}>
          {fmtPrice(currentPrice)}
        </span>
      )}

      <div style={{ width: 1, height: 24, background: '#30363d' }} />

      {/* Timeframe buttons */}
      <div style={{ display: 'flex', gap: 2 }}>
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => setTimeframe(tf)}
            style={{
              padding: '3px 8px',
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 3,
              border: 'none',
              cursor: 'pointer',
              background: timeframe === tf ? '#58a6ff' : '#21262d',
              color: timeframe === tf ? '#0d1117' : '#8b949e',
            }}
          >
            {tf}
          </button>
        ))}
      </div>

      <div style={{ width: 1, height: 24, background: '#30363d' }} />

      {/* P&L */}
      {pnl !== null && (
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: pnl >= 0 ? '#3fb950' : '#f85149',
          }}
        >
          P&L: {pnl >= 0 ? '+' : ''}
          {fmtPrice(pnl)}
        </span>
      )}

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Market session badge */}
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          padding: '3px 8px',
          borderRadius: 3,
          background: `${marketSession.color}22`,
          color: marketSession.color,
          border: `1px solid ${marketSession.color}44`,
          letterSpacing: 0.5,
        }}
      >
        {marketSession.label}
      </span>

      {/* Bot status badge */}
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          padding: '3px 8px',
          borderRadius: 3,
          background: botRunning ? '#3fb95022' : '#f8514922',
          color: botRunning ? '#3fb950' : '#f85149',
          border: `1px solid ${botRunning ? '#3fb95044' : '#f8514944'}`,
          letterSpacing: 0.5,
        }}
      >
        {botRunning ? 'RUNNING' : 'STOPPED'}
      </span>

      {/* PAPER badge */}
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          padding: '3px 8px',
          borderRadius: 3,
          background: '#58a6ff22',
          color: '#58a6ff',
          border: '1px solid #58a6ff44',
          letterSpacing: 0.5,
        }}
      >
        PAPER
      </span>

      {/* Online dot */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 5 }}
        title={online ? 'ONLINE' : 'OFFLINE'}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: online ? '#3fb950' : '#f85149',
          }}
        />
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: online ? '#3fb950' : '#f85149',
          }}
        >
          {online ? 'ONLINE' : 'OFFLINE'}
        </span>
      </div>

      <div style={{ width: 1, height: 24, background: '#30363d' }} />

      {/* Logout button */}
      <button
        onClick={() => supabase.auth.signOut()}
        title="Sign out"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 4,
          display: 'flex',
          alignItems: 'center',
          color: '#8b949e',
        }}
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
    </header>
  )
}
