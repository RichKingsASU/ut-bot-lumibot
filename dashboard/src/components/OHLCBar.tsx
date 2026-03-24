import React from 'react'
import type { OHLCV } from '../types/dashboard'
import { fmtPrice, fmtNumber, fmtTime } from '../utils/formatters'

interface OHLCBarProps {
  candle: OHLCV | null
  hoveredCandle?: OHLCV | null
}

export const OHLCBar: React.FC<OHLCBarProps> = ({ candle, hoveredCandle }) => {
  const data = hoveredCandle ?? candle

  if (!data) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', gap: '16px',
        padding: '4px 16px', background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border)', height: '28px',
        fontSize: '12px', color: 'var(--text-muted)',
      }}>
        <span>O — H — L — C — V —</span>
      </div>
    )
  }

  const isUp = data.close >= data.open
  const color = isUp ? 'var(--green)' : 'var(--red)'
  const change = data.close - data.open
  const changePct = data.open !== 0 ? (change / data.open) * 100 : 0
  const time = new Date(data.time * 1000)

  const cell = (label: string, val: string, c?: string) => (
    <span style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ color: c ?? 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontWeight: 500 }}>{val}</span>
    </span>
  )

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '16px',
      padding: '4px 16px', background: 'var(--bg-secondary)',
      borderBottom: '1px solid var(--border)', height: '28px', fontSize: '12px',
      flexShrink: 0,
    }}>
      <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
        {fmtTime(time)}
      </span>
      {cell('O', fmtPrice(data.open))}
      {cell('H', fmtPrice(data.high), 'var(--green)')}
      {cell('L', fmtPrice(data.low), 'var(--red)')}
      {cell('C', fmtPrice(data.close), color)}
      <span style={{ color, fontFamily: 'JetBrains Mono, monospace' }}>
        {change >= 0 ? '+' : ''}{fmtPrice(change)} ({changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%)
      </span>
      {cell('V', fmtNumber(data.volume))}
    </div>
  )
}
