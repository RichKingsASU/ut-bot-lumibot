import React, { useState } from 'react'
import type { Timeframe } from '../types/dashboard'
import { fmtPrice } from '../utils/formatters'
import { supabase } from '../lib/supabaseClient'
import { useTradingContext } from '../context/TradingContext'

const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '1D']

function formatUptime(seconds: number | null): string {
  if (seconds == null) return ''
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m.toString().padStart(2, '0')}m`
}

function formatSignalTime(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York' }) + ' ET'
  } catch { return '' }
}

export const TopBar: React.FC = () => {
  const {
    symbol, timeframe, currentPrice, prevClose,
    isInTrade, activePosition, connected,
    setSymbol, setTimeframe, botStatus
  } = useTradingContext()

  const botRunning = botStatus.online
  const tradeSide = activePosition?.side ?? null

  const [editingSymbol, setEditingSymbol] = useState(false)
  const [inputVal, setInputVal] = useState(symbol)

  const priceChange = (currentPrice ?? 0) - (prevClose ?? 0)
  const priceChangePct = (prevClose ?? 0) > 0 ? (priceChange / (prevClose ?? 1)) * 100 : 0
  const isUp = priceChange >= 0

  const handleSymbolSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const val = inputVal.trim().toUpperCase()
    if (val) { setSymbol(val); setEditingSymbol(false) }
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
        ${fmtPrice(currentPrice ?? 0)}
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
            onClick={() => setTimeframe(tf)}
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

      <span className={`badge ${botRunning ? 'badge-green' : botStatus.status === 'stale' ? 'badge-amber' : 'badge-gray'}`}>
        {botRunning && <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />}
        BOT {botRunning ? 'RUNNING' : botStatus.status === 'stale' ? 'STALE' : 'STOPPED'}
      </span>

      {isInTrade && (
        <span className="badge badge-green">
          <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
          IN TRADE — {tradeSide?.toUpperCase() ?? 'LONG'}
        </span>
      )}

      {/* Bot Status Indicator */}
      <span style={{
        color: botStatus.online ? 'var(--green)' : botStatus.status === 'stale' ? 'var(--amber)' : botStatus.status === 'connecting' ? 'var(--amber)' : 'var(--red)',
        fontSize: '11px', whiteSpace: 'nowrap'
      }}>
        ● {botStatus.online ? 'LIVE' : botStatus.status === 'stale' ? 'STALE' : botStatus.status === 'connecting' ? 'CONNECTING...' : 'OFFLINE'}
      </span>

      {/* Bot details when online */}
      {botStatus.online && (
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          {botStatus.symbol ?? ''} | {(botStatus.mode ?? '').toUpperCase()} | {formatUptime(botStatus.uptime_seconds)}
          {botStatus.last_signal && ` | ${botStatus.last_signal}`}
          {botStatus.last_signal_time && ` (${formatSignalTime(botStatus.last_signal_time)})`}
        </span>
      )}

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
