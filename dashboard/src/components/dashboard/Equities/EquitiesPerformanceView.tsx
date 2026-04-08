import React from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useTradingContext } from '../../../context/TradingContext'
import {
  calculateWinRate,
  calculateMaxDrawdown,
  calculateSharpe,
  sampleSizeWarning,
  type Trade,
} from '../../../utils/tradeStats'
import { HISTORICAL_TRADES } from '../../../data/historicalTrades'

const colors = {
  bgPrimary: '#0d1117',
  bgSecondary: '#161b22',
  bgTertiary: '#21262d',
  border: '#30363d',
  textPrimary: '#e6edf3',
  textMuted: '#8b949e',
  blue: '#58a6ff',
  green: '#3fb950',
  red: '#f85149',
  amber: '#e3b341',
}

const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

// Mock equity curve data (30 points)
const generateEquityCurve = () => {
  const data: { date: string; equity: number }[] = []
  let equity = 100000
  const now = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    equity += (Math.random() - 0.42) * 1200
    data.push({
      date: `${d.getMonth() + 1}/${d.getDate()}`,
      equity: Math.round(equity * 100) / 100,
    })
  }
  return data
}

const equityCurveData = generateEquityCurve()

// Trade history is sourced from the shared historicalTrades module so the
// Overview Win Rate card and this page's KPIs always agree.
const mockTrades = HISTORICAL_TRADES

export default function EquitiesPerformanceView() {
  const { account, loading } = useTradingContext()

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted }}>
        Loading performance data...
      </div>
    )
  }

  const totalPnl = mockTrades.reduce((sum, t) => sum + t.pnl, 0)
  const trades: Trade[] = mockTrades.map((t) => ({
    entry: t.entry,
    exit: t.exit,
    side: t.side as 'BUY' | 'SELL',
    pnl: t.pnl,
    date: t.date,
  }))
  const winRate = calculateWinRate(trades)
  const totalTrades = mockTrades.length
  const equityValues = trades.reduce((acc, t) => {
    const last = acc[acc.length - 1] || 100000
    acc.push(last + t.pnl)
    return acc
  }, [] as number[])
  const maxDrawdown = calculateMaxDrawdown(equityValues)
  const dailyReturns = trades.map((t) => t.pnl / 100000)
  const sharpeRatio = calculateSharpe(dailyReturns)
  const warning = sampleSizeWarning(totalTrades)

  const statCards = [
    { label: 'Total P&L', value: currency.format(totalPnl), color: totalPnl >= 0 ? colors.green : colors.red },
    { label: 'Win Rate', value: `${winRate}%`, color: colors.green },
    { label: 'Total Trades', value: String(totalTrades), color: colors.blue },
    { label: 'Sharpe Ratio', value: sharpeRatio.toFixed(2), color: colors.amber },
    { label: 'Max Drawdown', value: `${maxDrawdown}%`, color: colors.red },
  ]

  const handleExportCSV = () => {
    const headers = ['Date', 'Symbol', 'Side', 'Entry', 'Exit', 'P&L', 'Return %']
    const rows = mockTrades.map((t) => [t.date, t.symbol, t.side, t.entry, t.exit, t.pnl, t.returnPct])
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'trade_history.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div style={{ fontSize: 18, fontWeight: 600, color: colors.textPrimary }}>Performance</div>
        <button
          onClick={handleExportCSV}
          style={{
            padding: '8px 16px',
            borderRadius: 6,
            border: `1px solid ${colors.border}`,
            backgroundColor: colors.bgTertiary,
            color: colors.textPrimary,
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          Export CSV
        </button>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 24 }}>
        {statCards.map((card) => (
          <div
            key={card.label}
            style={{
              backgroundColor: colors.bgSecondary,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              padding: 18,
            }}
          >
            <div style={{ fontSize: 11, color: colors.textMuted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {card.label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 600, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* Equity Curve */}
      <div
        style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: 20,
          marginBottom: 24,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 16 }}>
          Equity Curve
        </div>
        <div style={{ height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={equityCurveData}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
              <XAxis dataKey="date" tick={{ fill: colors.textMuted, fontSize: 11 }} stroke={colors.border} />
              <YAxis
                tick={{ fill: colors.textMuted, fontSize: 11 }}
                stroke={colors.border}
                tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: colors.bgTertiary,
                  border: `1px solid ${colors.border}`,
                  borderRadius: 6,
                  color: colors.textPrimary,
                  fontSize: 12,
                }}
                formatter={(value) => [currency.format(Number(value)), 'Equity']}
              />
              <Line
                type="monotone"
                dataKey="equity"
                stroke={colors.blue}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: colors.blue }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trade History Table */}
      <div
        style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '14px 20px', fontSize: 14, fontWeight: 600, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
          Trade History
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Date', 'Symbol', 'Side', 'Entry', 'Exit', 'P&L', 'Return %'].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: 'left',
                    padding: '10px 16px',
                    fontSize: 11,
                    color: colors.textMuted,
                    borderBottom: `1px solid ${colors.border}`,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mockTrades.map((trade, i) => (
              <tr key={i}>
                <td style={{ padding: '10px 16px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                  {trade.date}
                </td>
                <td style={{ padding: '10px 16px', fontSize: 13, color: colors.textPrimary, fontWeight: 500, borderBottom: `1px solid ${colors.border}` }}>
                  {trade.symbol}
                </td>
                <td style={{ padding: '10px 16px', borderBottom: `1px solid ${colors.border}` }}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 10px',
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 600,
                      backgroundColor: trade.side === 'BUY' ? `${colors.green}22` : `${colors.red}22`,
                      color: trade.side === 'BUY' ? colors.green : colors.red,
                    }}
                  >
                    {trade.side}
                  </span>
                </td>
                <td style={{ padding: '10px 16px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                  {currency.format(trade.entry)}
                </td>
                <td style={{ padding: '10px 16px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                  {currency.format(trade.exit)}
                </td>
                <td
                  style={{
                    padding: '10px 16px',
                    fontSize: 13,
                    fontWeight: 500,
                    color: trade.pnl >= 0 ? colors.green : colors.red,
                    borderBottom: `1px solid ${colors.border}`,
                  }}
                >
                  {trade.pnl >= 0 ? '+' : ''}
                  {currency.format(trade.pnl)}
                </td>
                <td
                  style={{
                    padding: '10px 16px',
                    fontSize: 13,
                    fontWeight: 500,
                    color: trade.returnPct >= 0 ? colors.green : colors.red,
                    borderBottom: `1px solid ${colors.border}`,
                  }}
                >
                  {trade.returnPct >= 0 ? '+' : ''}
                  {trade.returnPct.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
