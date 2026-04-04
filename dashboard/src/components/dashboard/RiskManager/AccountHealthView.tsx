import React, { useState, useEffect } from 'react'
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { useTradingContext } from '../../../context/TradingContext'
import { DataFreshness } from '../../DataFreshness'
import {
  calculateWinRate,
  calculateMaxDrawdown,
  calculateSharpe,
  calculateSortino,
  calculateProfitFactor,
  sampleSizeWarning,
} from '../../../utils/tradeStats'

const AccountHealthView: React.FC = () => {
  const { account, signals } = useTradingContext()
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const equity = account ? parseFloat(account.equity) : 0
  const lastEquity = account ? parseFloat(account.last_equity) : 0
  const dailyPnL = equity - lastEquity
  const dailyTarget = 500
  const pnlPct = Math.min(Math.max((dailyPnL / dailyTarget) * 100, 0), 100)

  useEffect(() => {
    if (account) setLastUpdated(new Date())
  }, [account?.equity])

  // Derive trades from signal pairs
  const trades = React.useMemo(() => {
    const result: { entry: number; exit: number; side: 'BUY' | 'SELL'; pnl: number; date: string }[] = []
    for (let i = 0; i < signals.length - 1; i++) {
      if (signals[i].type === 'BUY') {
        const exit = signals.slice(i + 1).find((s) => s.type === 'SELL')
        if (exit) {
          const pnl = exit.price - signals[i].price
          result.push({
            entry: signals[i].price,
            exit: exit.price,
            side: 'BUY',
            pnl,
            date: new Date(signals[i].time * 1000).toISOString(),
          })
        }
      }
    }
    return result
  }, [signals])

  const winRate = calculateWinRate(trades)
  const equityValues = trades.length > 0
    ? trades.reduce((acc, t) => {
        const last = acc[acc.length - 1] || equity
        acc.push(last + t.pnl)
        return acc
      }, [] as number[])
    : [equity]
  const maxDrawdown = calculateMaxDrawdown(equityValues)

  const dailyReturns = trades.map((t) => t.pnl / (equity || 1))
  const sharpe = calculateSharpe(dailyReturns)
  const sortino = calculateSortino(dailyReturns)
  const profitFactor = calculateProfitFactor(trades)
  const sampleWarning = sampleSizeWarning(trades.length)

  // Current drawdown from account
  const currentDrawdown = equity > 0 && lastEquity > 0
    ? Math.round(((equity - lastEquity) / lastEquity) * 10000) / 100
    : 0

  // Risk score: ratio of current drawdown to a 10% max drawdown limit
  const maxDrawdownLimit = 10
  const riskScore = Math.min(100, Math.round((Math.abs(maxDrawdown) / maxDrawdownLimit) * 100))

  const getRiskColor = (score: number) => {
    if (score < 30) return '#3fb950'
    if (score <= 60) return '#e3b341'
    return '#f85149'
  }

  const getRiskLabel = (score: number) => {
    if (score < 30) return 'Low Risk'
    if (score <= 60) return 'Moderate Risk'
    return 'High Risk'
  }

  const riskColor = getRiskColor(riskScore)

  const STAT_CARDS = [
    { label: 'Current Drawdown', value: `${currentDrawdown >= 0 ? '+' : ''}${currentDrawdown}%`, color: currentDrawdown >= 0 ? '#3fb950' : '#e3b341' },
    { label: 'Max Drawdown', value: `${maxDrawdown}%`, color: '#f85149' },
    { label: 'Sharpe Ratio', value: sharpe.toFixed(2), color: '#3fb950' },
    { label: 'Sortino Ratio', value: sortino.toFixed(2), color: '#3fb950' },
    { label: 'Win Rate', value: `${winRate}%`, color: '#58a6ff' },
    { label: 'Profit Factor', value: profitFactor === Infinity ? 'N/A' : profitFactor.toFixed(2), color: '#3fb950' },
  ]

  // Generate equity curve from account data (placeholder until portfolio_snapshots is wired)
  const EQUITY_DATA = React.useMemo(() => {
    if (!account) return []
    const base = parseFloat(account.equity)
    const data = []
    for (let i = 0; i < 30; i++) {
      const date = new Date()
      date.setDate(date.getDate() - (29 - i))
      data.push({
        date: `${date.getMonth() + 1}/${date.getDate()}`,
        equity: i === 29 ? base : base, // Flat line until portfolio_snapshots is connected
        drawdown: 0,
      })
    }
    return data
  }, [account?.equity])

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Account Health</h2>
        <DataFreshness lastUpdated={lastUpdated} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20, marginBottom: 20 }}>
        {/* Risk Score Gauge */}
        <div style={{
          backgroundColor: 'var(--bg-secondary, #161b22)',
          border: '1px solid var(--border, #30363d)',
          borderRadius: 8, padding: 24,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{ fontSize: 13, color: 'var(--text-muted, #8b949e)', marginBottom: 12, fontWeight: 500 }}>
            Risk Score
          </div>
          <div style={{
            width: 120, height: 120, borderRadius: '50%',
            border: `6px solid ${riskColor}`,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 0 24px ${riskColor}33`,
          }}>
            <div style={{ fontSize: 40, fontWeight: 800, color: riskColor, lineHeight: 1 }}>
              {riskScore}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted, #8b949e)', marginTop: 2 }}>/100</div>
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: riskColor, marginTop: 12 }}>
            {getRiskLabel(riskScore)}
          </div>
        </div>

        {/* Stat Cards Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {STAT_CARDS.map(card => (
            <div key={card.label} style={{
              backgroundColor: 'var(--bg-secondary, #161b22)',
              border: '1px solid var(--border, #30363d)',
              borderRadius: 8, padding: 18,
              display: 'flex', flexDirection: 'column', justifyContent: 'center',
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)', marginBottom: 6, fontWeight: 500 }}>
                {card.label}
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, color: card.color }}>
                {card.value}
              </div>
              {sampleWarning && (card.label === 'Sharpe Ratio' || card.label === 'Win Rate' || card.label === 'Sortino Ratio') && (
                <div style={{ fontSize: 10, color: 'var(--text-muted, #8b949e)', marginTop: 4 }}>
                  {sampleWarning}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Daily P&L Progress */}
      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, padding: 20, marginBottom: 20,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-muted, #8b949e)', marginBottom: 2 }}>Daily P&L Progress</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted, #8b949e)' }}>Target: ${dailyTarget.toLocaleString()}</div>
          </div>
          <div style={{
            fontSize: 22, fontWeight: 700,
            color: dailyPnL >= 0 ? '#3fb950' : '#f85149',
          }}>
            {dailyPnL >= 0 ? '+' : ''}${dailyPnL.toLocaleString()}
          </div>
        </div>
        <div style={{
          height: 12, borderRadius: 6,
          backgroundColor: 'var(--bg-tertiary, #21262d)',
          overflow: 'hidden',
          position: 'relative',
        }}>
          <div style={{
            width: `${pnlPct}%`,
            height: '100%',
            borderRadius: 6,
            backgroundColor: dailyPnL >= 0 ? '#3fb950' : '#f85149',
            transition: 'width 0.5s ease',
          }} />
          <div style={{
            position: 'absolute', top: -2, right: 0, width: 2, height: 16,
            backgroundColor: 'var(--text-muted, #8b949e)',
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--text-muted, #8b949e)' }}>
          <span>$0</span>
          <span>{Math.round(pnlPct)}% of target</span>
          <span>${dailyTarget.toLocaleString()}</span>
        </div>
      </div>

      {/* Equity Curve with Drawdown Overlay */}
      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, padding: 24,
      }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>
          Equity Curve & Drawdown (30 Days)
        </h3>
        {EQUITY_DATA.length === 0 ? (
          <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: 13, padding: '40px 0', textAlign: 'center' }}>
            No account data available. Connect Alpaca API to view equity curve.
          </div>
        ) : (
          <div style={{ width: '100%', height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={EQUITY_DATA}>
                <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#8b949e', fontSize: 11 }}
                  axisLine={{ stroke: '#30363d' }}
                  tickLine={false}
                  interval={4}
                />
                <YAxis
                  yAxisId="equity"
                  tick={{ fill: '#8b949e', fontSize: 11 }}
                  axisLine={{ stroke: '#30363d' }}
                  tickLine={false}
                  domain={['auto', 'auto']}
                  tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
                />
                <YAxis
                  yAxisId="drawdown"
                  orientation="right"
                  tick={{ fill: '#8b949e', fontSize: 11 }}
                  axisLine={{ stroke: '#30363d' }}
                  tickLine={false}
                  domain={['auto', 0]}
                  tickFormatter={(v: number) => `${v}%`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: 6,
                    color: '#e6edf3',
                  }}
                  labelStyle={{ color: '#8b949e' }}
                  formatter={(value, name) => {
                    const v = Number(value)
                    if (name === 'equity') return [`$${v.toLocaleString()}`, 'Equity']
                    return [`${v}%`, 'Drawdown']
                  }}
                />
                <Area
                  yAxisId="drawdown"
                  type="monotone"
                  dataKey="drawdown"
                  stroke="#f8514966"
                  fill="rgba(248, 81, 73, 0.1)"
                  strokeWidth={1}
                />
                <Line
                  yAxisId="equity"
                  type="monotone"
                  dataKey="equity"
                  stroke="#58a6ff"
                  strokeWidth={2}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}

export default AccountHealthView
