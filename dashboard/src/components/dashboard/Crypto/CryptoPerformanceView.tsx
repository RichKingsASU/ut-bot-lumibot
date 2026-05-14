import React, { useState } from 'react'
import { TrendingUp, TrendingDown, Download, DollarSign, Target, BarChart3, Award, AlertTriangle } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { PageHeader } from '../../ui/PageHeader'

interface CryptoTrade {
  id: number
  date: string
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: number
  entryPrice: number
  exitPrice: number
  pnl: number
  pnlPercent: number
}

const mockTrades: CryptoTrade[] = [
  { id: 1, date: '2026-03-25', symbol: 'BTC', side: 'BUY', quantity: 0.15, entryPrice: 65200, exitPrice: 67400, pnl: 330.0, pnlPercent: 3.37 },
  { id: 2, date: '2026-03-26', symbol: 'ETH', side: 'BUY', quantity: 2.5, entryPrice: 3480, exitPrice: 3380, pnl: -250.0, pnlPercent: -2.87 },
  { id: 3, date: '2026-03-27', symbol: 'SOL', side: 'BUY', quantity: 20, entryPrice: 132, exitPrice: 145, pnl: 260.0, pnlPercent: 9.85 },
  { id: 4, date: '2026-03-28', symbol: 'BTC', side: 'SELL', quantity: 0.1, entryPrice: 67800, exitPrice: 66900, pnl: 90.0, pnlPercent: 1.33 },
  { id: 5, date: '2026-03-29', symbol: 'ETH', side: 'BUY', quantity: 3.0, entryPrice: 3520, exitPrice: 3610, pnl: 270.0, pnlPercent: 2.56 },
  { id: 6, date: '2026-03-30', symbol: 'SOL', side: 'BUY', quantity: 15, entryPrice: 148, exitPrice: 139, pnl: -135.0, pnlPercent: -6.08 },
  { id: 7, date: '2026-03-31', symbol: 'BTC', side: 'BUY', quantity: 0.08, entryPrice: 66500, exitPrice: 68200, pnl: 136.0, pnlPercent: 2.56 },
  { id: 8, date: '2026-04-01', symbol: 'ETH', side: 'SELL', quantity: 1.5, entryPrice: 3600, exitPrice: 3550, pnl: 75.0, pnlPercent: 1.39 },
]

const equityCurveData = [
  { date: 'Mar 25', equity: 10000 },
  { date: 'Mar 26', equity: 10330 },
  { date: 'Mar 27', equity: 10080 },
  { date: 'Mar 28', equity: 10340 },
  { date: 'Mar 29', equity: 10430 },
  { date: 'Mar 30', equity: 10700 },
  { date: 'Mar 31', equity: 10565 },
  { date: 'Apr 01', equity: 10701 },
  { date: 'Apr 02', equity: 10776 },
]

// Format P&L so negatives render as "-$250.00" not "$-250.00", and
// positives render with a leading "+". Used everywhere a P&L number is
// shown so the formatting stays consistent across the page.
const formatPnl = (n: number): string =>
  n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`

// Format quantities with the asset's base unit so the Qty column can
// never be visually confused with a USD price column.
const formatQty = (qty: number, symbol: string): string => {
  // BTC ≈ 8 decimals, ETH/SOL ≈ 4
  const decimals = symbol === 'BTC' ? 4 : symbol === 'ETH' ? 4 : 2
  return `${qty.toFixed(decimals)} ${symbol}`
}

const CryptoPerformanceView: React.FC = () => {
  const totalPnl = mockTrades.reduce((sum, t) => sum + t.pnl, 0)
  const wins = mockTrades.filter(t => t.pnl > 0).length
  const winRate = ((wins / mockTrades.length) * 100).toFixed(1)
  const bestTrade = Math.max(...mockTrades.map(t => t.pnl))
  const worstTrade = Math.min(...mockTrades.map(t => t.pnl))

  const stats = [
    { label: 'Total Crypto P&L', value: formatPnl(totalPnl), icon: DollarSign, color: totalPnl >= 0 ? 'var(--green, #3fb950)' : 'var(--red, #f85149)' },
    { label: 'Win Rate', value: `${winRate}%`, icon: Target, color: 'var(--blue, #58a6ff)' },
    { label: 'Total Trades', value: `${mockTrades.length}`, icon: BarChart3, color: 'var(--text-primary, #e6edf3)' },
    { label: 'Best Trade', value: formatPnl(bestTrade), icon: Award, color: 'var(--green, #3fb950)' },
    { label: 'Worst Trade', value: formatPnl(worstTrade), icon: AlertTriangle, color: 'var(--red, #f85149)' },
  ]

  const handleExportCSV = () => {
    const header = 'ID,Date,Symbol,Side,Quantity,Entry Price,Exit Price,P&L,P&L %\n'
    const rows = mockTrades
      .map(t => `${t.id},${t.date},${t.symbol},${t.side},${t.quantity},${t.entryPrice},${t.exitPrice},${t.pnl},${t.pnlPercent}`)
      .join('\n')
    const blob = new Blob([header + rows], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'crypto_trades.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const cardStyle: React.CSSProperties = {
    background: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '12px',
    padding: '20px',
  }

  return (
    <div style={{ padding: '24px', background: 'var(--bg-primary, #0d1117)', minHeight: '100vh', color: 'var(--text-primary, #e6edf3)' }}>
      <PageHeader
        title="Crypto performance"
        subtitle="Paper account results"
        actions={
          <button
            onClick={handleExportCSV}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              background: 'var(--bg-tertiary, #21262d)',
              border: '1px solid var(--border, #30363d)',
              borderRadius: '8px',
              color: 'var(--text-primary, #e6edf3)',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            <Download size={14} />
            Export CSV
          </button>
        }
      />

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px', marginBottom: '24px' }}>
        {stats.map(stat => (
          <div key={stat.label} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <stat.icon size={16} style={{ color: stat.color }} />
              <span style={{ color: 'var(--text-muted, #8b949e)', fontSize: '12px' }}>{stat.label}</span>
            </div>
            <div style={{ fontSize: '22px', fontWeight: 700, color: stat.color }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Equity curve */}
      <div style={{ ...cardStyle, marginBottom: '24px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px 0' }}>Equity Curve</h2>
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={equityCurveData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #30363d)" />
              <XAxis dataKey="date" stroke="var(--text-muted, #8b949e)" fontSize={12} />
              <YAxis
                stroke="var(--text-muted, #8b949e)"
                fontSize={12}
                domain={['dataMin - 100', 'dataMax + 100']}
                tickFormatter={(v: number) => `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-tertiary, #21262d)',
                  border: '1px solid var(--border, #30363d)',
                  borderRadius: '8px',
                  color: 'var(--text-primary, #e6edf3)',
                }}
              />
              <Line type="monotone" dataKey="equity" stroke="var(--blue, #58a6ff)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trade history */}
      <div style={cardStyle}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px 0' }}>Trade History</h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border, #30363d)' }}>
                {['Date', 'Symbol', 'Side', 'Qty', 'Entry', 'Exit', 'P&L', 'P&L %'].map(h => (
                  <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-muted, #8b949e)', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {mockTrades.map(trade => (
                <tr key={trade.id} style={{ borderBottom: '1px solid var(--border, #30363d)' }}>
                  <td style={{ padding: '10px 12px' }}>{trade.date}</td>
                  <td style={{ padding: '10px 12px', fontWeight: 600 }}>{trade.symbol}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        background: trade.side === 'BUY' ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)',
                        color: trade.side === 'BUY' ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                      }}
                    >
                      {trade.side}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px' }}>{formatQty(trade.quantity, trade.symbol)}</td>
                  <td style={{ padding: '10px 12px' }}>${trade.entryPrice.toLocaleString()}</td>
                  <td style={{ padding: '10px 12px' }}>${trade.exitPrice.toLocaleString()}</td>
                  <td
                    style={{
                      padding: '10px 12px',
                      fontWeight: 600,
                      color: trade.pnl >= 0 ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                    }}
                  >
                    {formatPnl(trade.pnl)}
                  </td>
                  <td
                    style={{
                      padding: '10px 12px',
                      color: trade.pnlPercent >= 0 ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                    }}
                  >
                    {trade.pnlPercent >= 0 ? '+' : ''}{trade.pnlPercent}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default CryptoPerformanceView
