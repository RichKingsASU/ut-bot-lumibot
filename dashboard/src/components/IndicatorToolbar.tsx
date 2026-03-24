import React from 'react'
import type { IndicatorState } from '../types/dashboard'

interface IndicatorToolbarProps {
  indicators: IndicatorState
  onChange: (key: keyof IndicatorState) => void
}

const INDICATOR_CONFIG: Array<{
  key: keyof IndicatorState
  label: string
  color: string
  defaultOn: boolean
}> = [
  { key: 'atrStop', label: 'ATR Stop', color: '#58a6ff', defaultOn: true },
  { key: 'signals', label: 'Signals', color: '#3fb950', defaultOn: true },
  { key: 'volume', label: 'Volume', color: '#8b949e', defaultOn: true },
  { key: 'srLines', label: 'S/R Lines', color: '#e3b341', defaultOn: true },
  { key: 'ema9', label: 'EMA 9', color: '#e6edf3', defaultOn: false },
  { key: 'ema21', label: 'EMA 21', color: '#f0883e', defaultOn: false },
  { key: 'vwap', label: 'VWAP', color: '#6e40c9', defaultOn: false },
  { key: 'rsi', label: 'RSI', color: '#d2a8ff', defaultOn: false },
  { key: 'macd', label: 'MACD', color: '#79c0ff', defaultOn: false },
  { key: 'bollinger', label: 'BB', color: '#58a6ff', defaultOn: false },
]

export const IndicatorToolbar: React.FC<IndicatorToolbarProps> = ({ indicators, onChange }) => {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '6px',
      padding: '4px 12px',
      background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border)',
      flexShrink: 0, flexWrap: 'wrap', height: '32px',
      overflowX: 'auto',
    }}>
      {INDICATOR_CONFIG.map(({ key, label, color }) => {
        const active = indicators[key]
        return (
          <button
            key={key}
            id={`ind-${key}`}
            onClick={() => onChange(key)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '2px 8px',
              borderRadius: '4px',
              border: active ? `1px solid ${color}66` : '1px solid var(--border)',
              background: active ? `${color}18` : 'transparent',
              color: active ? color : 'var(--text-muted)',
              fontSize: '11px',
              fontWeight: 500,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: active ? color : 'var(--border)',
              flexShrink: 0,
            }} />
            {label}
          </button>
        )
      })}
    </div>
  )
}
