import React, { useState, useEffect } from 'react'
import type { AlpacaPosition } from '../types/alpaca'
import { fmtCurrency, fmtPnL, fmtPercent, fmtPrice, fmtDuration, fmtShares, fmtDateTime } from '../utils/formatters'

interface InTradeBarProps {
  isInTrade: boolean
  position: AlpacaPosition | null
  currentPrice: number
  trailStop: number
  entryTime?: string
}

export const InTradeBar: React.FC<InTradeBarProps> = ({
  isInTrade, position, currentPrice, trailStop, entryTime,
}) => {
  const [, forceUpdate] = useState(0)

  // Live timer
  useEffect(() => {
    const t = setInterval(() => forceUpdate((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [])

  if (!isInTrade || !position) {
    return (
      <div style={{
        padding: '6px 16px', background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: '8px',
        flexShrink: 0, height: '30px',
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--border)', display: 'inline-block' }} />
        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>No active position</span>
      </div>
    )
  }

  const unrealizedPl = parseFloat(position.unrealized_pl)
  const unrealizedPlPct = parseFloat(position.unrealized_plpc)
  const entryPrice = parseFloat(position.avg_entry_price)
  const qty = parseFloat(position.qty)
  const stopDist = currentPrice - trailStop
  const stopDistPct = entryPrice > 0 ? stopDist / entryPrice : 0

  let riskColor = 'var(--green)'
  let riskLabel = 'SAFE'
  if (Math.abs(stopDist) < 0.05) { riskColor = 'var(--red)'; riskLabel = 'STOP HIT' }
  else if (Math.abs(stopDist) < 0.20) { riskColor = 'var(--amber)'; riskLabel = 'NEAR STOP' }

  const plIsPos = unrealizedPl >= 0

  const sep = <div style={{ width: '1px', height: '28px', background: 'var(--border)', flexShrink: 0 }} />

  const block = (label: string, value: React.ReactNode, color?: string) => (
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 12px', minWidth: 'fit-content' }}>
      <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '1px', whiteSpace: 'nowrap' }}>{label}</span>
      <span style={{ fontSize: '13px', fontWeight: 600, color: color ?? 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'nowrap' }}>{value}</span>
    </div>
  )

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 0,
      background: '#0d1f0d',
      borderBottom: '2px solid #2ea043',
      height: '50px', flexShrink: 0, overflowX: 'auto', overflowY: 'hidden',
    }}>
      {/* IN TRADE label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '0 16px', flexShrink: 0 }}>
        <span className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
        <span style={{ color: 'var(--green)', fontWeight: 700, fontSize: '12px', letterSpacing: '0.08em' }}>IN TRADE</span>
      </div>
      {sep}
      {block('UNREALIZED P&L', fmtPnL(unrealizedPl), plIsPos ? 'var(--green)' : 'var(--red)')}
      {sep}
      {block('P&L %', fmtPercent(unrealizedPlPct), plIsPos ? 'var(--green)' : 'var(--red)')}
      {sep}
      {block('ENTRY', `$${fmtPrice(entryPrice)}`)}
      {sep}
      {block('CURRENT', `$${fmtPrice(currentPrice)}`)}
      {sep}
      {block('SHARES', fmtShares(qty))}
      {sep}
      {block('STOP DIST', `$${fmtPrice(Math.abs(stopDist))} / ${(Math.abs(stopDistPct) * 100).toFixed(2)}%`,
        Math.abs(stopDist) < 0.05 ? 'var(--red)' : Math.abs(stopDist) < 0.20 ? 'var(--amber)' : 'var(--text-primary)'
      )}
      {sep}
      {block('DURATION', entryTime ? fmtDuration(entryTime) : '—')}
      {sep}
      {/* Risk chip */}
      <div style={{ padding: '0 12px' }}>
        <span className="badge" style={{
          background: `${riskColor}22`, color: riskColor,
          border: `1px solid ${riskColor}55`, fontSize: '11px', fontWeight: 700,
        }}>{riskLabel}</span>
      </div>
      {sep}
      {entryTime && block('ENTRY TIME', fmtDateTime(entryTime), 'var(--text-muted)')}
    </div>
  )
}
