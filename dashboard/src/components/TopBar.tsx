import React, { useState } from 'react'
import type { Timeframe } from '../types/dashboard'
import { fmtPrice } from '../utils/formatters'
import { supabase } from '../lib/supabaseClient'


interface TopBarProps {
  symbol: string
  timeframe: Timeframe
  currentPrice: number
  prevClose: number
  isInTrade: boolean
  tradeSide: 'long' | 'short' | null
  botRunning: boolean
  connected: boolean
  onSymbolChange: (s: string) => void
  onTimeframeChange: (t: Timeframe) => void
}

const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '1D']

export const TopBar: React.FC<TopBarProps> = ({
  symbol, timeframe, currentPrice, prevClose,
  isInTrade, tradeSide, botRunning, connected,
  onSymbolChange, onTimeframeChange,
}) => {
  const [editingSymbol, setEditingSymbol] = useState(false)
  const [inputVal, setInputVal] = useState(symbol)

  const priceChange = currentPrice - prevClose
  const priceChangePct = prevClose > 0 ? (priceChange / prevClose) * 100 : 0
  const isUp = priceChange >= 0

  const handleSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const val = inputVal.trim().toUpperCase()
    if (val) { onSymbolChange(val); setEditingSymbol(false) }
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '0 16px',
        height: '48px',
        background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
        overflow: 'hidden',
      }}
    >
      {/* Logo */}
      <span style={{ color: 'var(--blue)', fontWeight: 700, fontSize: '14px', whiteSpace: 'nowrap', letterSpacing: '0.05em' }}>
        ◆ DISRUPTING ALPHA
      </span>

      <div style={{ width: '1px', height: '20px', background: 'var(--border)' }} />

      {/* Symbol Pill */}
      {editingSymbol ? (
        <form onSubmit={handleSymbolSubmit}>
          <input
            autoFocus
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value.toUpperCase())}
            onBlur={() => { setEditingSymbol(false); setInputVal(symbol) }}
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--blue)',
              color: 'var(--text-primary)',
              borderRadius: '4px',
              padding: '2px 8px',
              fontSize: '13px',
              fontWeight: 600,
              width: '80px',
              outline: 'none',
            }}
          />
        </form>
      ) : (
        <button
          onClick={() => { setEditingSymbol(true); setInputVal(symbol) }}
          style={{
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
            borderRadius: '4px',
            padding: '2px 10px',
            fontSize: '13px',
            fontWeight: 700,
            cursor: 'pointer',
          }}
          id="symbol-pill"
        >
          {symbol}
        </button>
      )}

      {/* Price */}
      <span style={{ fontSize: '16px', fontWeight: 700, color: isUp ? 'var(--green)' : 'var(--red)', fontFamily: 'JetBrains Mono, monospace' }}>
        ${fmtPrice(currentPrice)}
      </span>
      <span style={{ color: isUp ? 'var(--green)' : 'var(--red)', fontSize: '12px' }}>
        {isUp ? '+' : ''}{fmtPrice(priceChange)} ({isUp ? '+' : ''}{priceChangePct.toFixed(2)}%)
      </span>

      <div style={{ flex: 1 }} />

      {/* Timeframes */}
      <div style={{ display: 'flex', gap: '2px' }}>
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            id={`tf-btn-${tf}`}
            onClick={() => onTimeframeChange(tf)}
            style={{
              background: timeframe === tf ? 'rgba(88,166,255,0.2)' : 'transparent',
              border: timeframe === tf ? '1px solid var(--blue)' : '1px solid transparent',
              color: timeframe === tf ? 'var(--blue)' : 'var(--text-muted)',
              borderRadius: '4px',
              padding: '2px 8px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >{tf}</button>
        ))}
      </div>

      <div style={{ width: '1px', height: '20px', background: 'var(--border)' }} />

      {/* Badges */}
      <span className={`badge badge-blue`}>PAPER</span>

      <span className={`badge ${botRunning ? 'badge-green' : 'badge-gray'}`}>
        {botRunning && <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />}
        BOT {botRunning ? 'RUNNING' : 'STOPPED'}
      </span>

      {isInTrade && (
        <span className="badge badge-green">
          <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
          IN TRADE — {tradeSide?.toUpperCase() ?? 'LONG'}
        </span>
      )}

      {/* Connection */}
      <span style={{ color: connected ? 'var(--green)' : 'var(--red)', fontSize: '11px', whiteSpace: 'nowrap' }}>
        ● {connected ? 'LIVE' : 'OFFLINE'}
      </span>

      <div style={{ width: '1px', height: '20px', background: 'var(--border)' }} />

      {/* Logout */}
      <button
        onClick={() => supabase.auth.signOut()}
        title="Logout"
        style={{
          background: 'transparent',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          padding: '4px',
          display: 'flex',
          alignItems: 'center',
          transition: 'color 0.2s',
        }}
        onMouseOver={(e) => (e.currentTarget.style.color = '#fff')}
        onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
      </button>
    </div>

  )
}
