import React from 'react'
import type { AlpacaPosition } from '../../types/alpaca'
import { fmtCurrency, fmtPnL, fmtPercent, fmtPrice, fmtShares, fmtDuration } from '../../utils/formatters'

interface ActiveTradeProps {
  position: AlpacaPosition | null
  currentPrice: number
  trailStop: number
  lastSignal: string
}

export const ActiveTrade: React.FC<ActiveTradeProps> = ({ position, currentPrice, trailStop, lastSignal }) => {
  if (!position) {
    return (
      <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
        No active position
      </div>
    )
  }

  const entry = parseFloat(position.avg_entry_price)
  const qty = parseFloat(position.qty)
  const positionValue = parseFloat(position.market_value)
  const unrealPl = parseFloat(position.unrealized_pl)
  const unrealPlPct = parseFloat(position.unrealized_plpc)
  const stopDist = Math.abs(currentPrice - trailStop)
  const riskIfStopped = stopDist * qty
  const rr = unrealPl > 0 && riskIfStopped > 0 ? (unrealPl / riskIfStopped).toFixed(2) : '—'
  const isLong = position.side === 'long'

  const row = (label: string, val: React.ReactNode, color?: string) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{label}</span>
      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, fontWeight: 500, color: color ?? 'var(--text-primary)' }}>{val}</span>
    </div>
  )

  return (
    <div style={{ padding: '8px 12px', borderLeft: '3px solid var(--green)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>{position.symbol}</span>
        <span className={`badge ${isLong ? 'badge-green' : 'badge-red'}`}>{isLong ? 'LONG' : 'SHORT'}</span>
      </div>

      {row('Entry Price', `$${fmtPrice(entry)}`)}
      {row('Current Price', `$${fmtPrice(currentPrice)}`)}
      {row('Shares', fmtShares(qty))}
      {row('Position Value', fmtCurrency(positionValue))}
      {row('Unrealized P&L', fmtPnL(unrealPl), unrealPl >= 0 ? 'var(--green)' : 'var(--red)')}
      {row('P&L %', fmtPercent(unrealPlPct), unrealPlPct >= 0 ? 'var(--green)' : 'var(--red)')}
      {row('Trail Stop', `$${fmtPrice(trailStop)}`)}
      {row('Stop Distance', `$${fmtPrice(stopDist)}`)}
      {row('Risk if Stopped', fmtCurrency(riskIfStopped), 'var(--red)')}
      {row('R:R Ratio', `${rr}R`)}
      {row('Entry Signal', lastSignal || '—', 'var(--blue)')}

      <div style={{ marginTop: 8 }}>
        <div className="progress-bar">
          <div className="progress-bar-fill" style={{
            width: `${Math.min(Math.max((unrealPl / Math.max(unrealPl, 0.01)) * 100, 0), 100)}%`,
            background: unrealPl >= 0 ? 'var(--green)' : 'var(--red)',
          }} />
        </div>
      </div>
    </div>
  )
}
