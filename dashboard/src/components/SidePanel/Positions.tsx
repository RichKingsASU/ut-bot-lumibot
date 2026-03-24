import React from 'react'
import type { AlpacaPosition } from '../../types/alpaca'
import { fmtCurrency, fmtPnL, fmtPercent, fmtPrice, fmtShares } from '../../utils/formatters'

interface PositionsProps {
  positions: AlpacaPosition[]
}

export const Positions: React.FC<PositionsProps> = ({ positions }) => {
  if (positions.length === 0) {
    return <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>No open positions</div>
  }

  const totalUnreal = positions.reduce((s, p) => s + parseFloat(p.unrealized_pl), 0)

  return (
    <div style={{ overflow: 'auto', maxHeight: '100%' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: 10 }}>
            <th style={{ padding: '6px 8px', textAlign: 'left' }}>Symbol</th>
            <th style={{ padding: '6px 4px', textAlign: 'right' }}>Shares</th>
            <th style={{ padding: '6px 4px', textAlign: 'right' }}>Avg Entry</th>
            <th style={{ padding: '6px 4px', textAlign: 'right' }}>Price</th>
            <th style={{ padding: '6px 4px', textAlign: 'right' }}>P&L $</th>
            <th style={{ padding: '6px 8px', textAlign: 'right' }}>P&L %</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const pl = parseFloat(p.unrealized_pl)
            const plPct = parseFloat(p.unrealized_plpc)
            const color = pl >= 0 ? 'var(--green)' : 'var(--red)'
            return (
              <tr key={p.asset_id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '5px 8px', fontWeight: 700, color: 'var(--text-primary)' }}>{p.symbol}</td>
                <td style={{ padding: '5px 4px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace' }}>{fmtShares(parseFloat(p.qty))}</td>
                <td style={{ padding: '5px 4px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace' }}>${fmtPrice(parseFloat(p.avg_entry_price))}</td>
                <td style={{ padding: '5px 4px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace' }}>${fmtPrice(parseFloat(p.current_price))}</td>
                <td style={{ padding: '5px 4px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', color }}>{fmtPnL(pl)}</td>
                <td style={{ padding: '5px 8px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', color }}>{fmtPercent(plPct)}</td>
              </tr>
            )
          })}
          <tr style={{ background: 'var(--bg-tertiary)', fontWeight: 600 }}>
            <td colSpan={4} style={{ padding: '5px 8px', fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Total Unrealized</td>
            <td colSpan={2} style={{ padding: '5px 8px', textAlign: 'right', fontFamily: 'JetBrains Mono, monospace', color: totalUnreal >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {fmtPnL(totalUnreal)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
