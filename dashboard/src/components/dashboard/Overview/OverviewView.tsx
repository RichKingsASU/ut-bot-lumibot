import React, { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Briefcase, Target } from 'lucide-react'
import { useTradingContext } from '../../../context/TradingContext'
import { DataFreshness } from '../../DataFreshness'
import { calculateAllTimeWinRate } from '../../../data/historicalTrades'
import { formatTimestamp } from '../../../lib/time'
import { PageHeader } from '../../ui/PageHeader'

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

export default function OverviewView() {
  const {
    account,
    positions,
    signals,
    logs,
    connected,
    botStatus,
    loading,
  } = useTradingContext()

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  useEffect(() => {
    if (account) setLastUpdated(new Date())
  }, [account?.equity])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted }}>
        Loading dashboard data...
      </div>
    )
  }

  const equity = account ? parseFloat(account.equity) : 0
  const lastEquity = account ? parseFloat(account.last_equity) : 0
  const dayPnl = equity - lastEquity
  const dayPnlPct = lastEquity !== 0 ? (dayPnl / lastEquity) * 100 : 0
  const openPositions = positions.length

  // Win Rate is sourced from the historical trade log (same source as the
  // Performance page) so both screens always show the same number. The old
  // implementation read from live session signals which had 0 trades and
  // therefore always rendered 0%.
  const winRate = calculateAllTimeWinRate()

  const statCards = [
    { label: 'Total Equity', value: currency.format(equity), icon: DollarSign, color: colors.blue },
    {
      label: 'Day P&L',
      value: `${dayPnl >= 0 ? '+' : ''}${currency.format(dayPnl)} (${dayPnlPct >= 0 ? '+' : ''}${dayPnlPct.toFixed(2)}%)`,
      icon: TrendingUp,
      color: dayPnl >= 0 ? colors.green : colors.red,
    },
    { label: 'Open Positions', value: String(openPositions), icon: Briefcase, color: colors.amber },
    { label: 'Win Rate (all time)', value: `${winRate}%`, icon: Target, color: colors.green },
  ]

  const recentSignals = [...signals].reverse().slice(0, 10)
  const recentLogs = [...logs].reverse().slice(0, 5)

  const connectionItems = [
    { name: 'Alpaca', online: connected },
    { name: 'Database', online: true },
    { name: 'Bot Engine', online: botStatus.online },
  ]

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      <PageHeader
        title="Overview"
        subtitle="Live trading dashboard"
        actions={<DataFreshness lastUpdated={lastUpdated} />}
      />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <div
              key={card.label}
              style={{
                backgroundColor: colors.bgSecondary,
                border: `1px solid ${colors.border}`,
                borderRadius: 8,
                padding: 20,
                display: 'flex',
                alignItems: 'center',
                gap: 16,
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 8,
                  backgroundColor: `${card.color}18`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon size={22} color={card.color} />
              </div>
              <div>
                <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 4 }}>{card.label}</div>
                <div style={{ fontSize: 18, fontWeight: 600, color: colors.textPrimary }}>{card.value}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Connection Health + Recent Signals row */}
      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, marginBottom: 24 }}>
        {/* Connection Health */}
        <div
          style={{
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            padding: 20,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 16 }}>
            Connection Health
          </div>
          {connectionItems.map((item) => (
            <div
              key={item.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 0',
                borderBottom: `1px solid ${colors.border}`,
              }}
            >
              <span style={{ color: colors.textPrimary, fontSize: 13 }}>{item.name}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: item.online ? colors.green : colors.red,
                  }}
                />
                <span style={{ fontSize: 12, color: item.online ? colors.green : colors.red }}>
                  {item.online ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Recent Signals */}
        <div
          style={{
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            padding: 20,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 16 }}>
            Recent Signals
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Time', 'Type', 'Price'].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: 'left',
                      padding: '8px 12px',
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
              {recentSignals.length === 0 && (
                <tr>
                  <td colSpan={3} style={{ padding: 16, color: colors.textMuted, textAlign: 'center', fontSize: 13 }}>
                    No signals yet
                  </td>
                </tr>
              )}
              {recentSignals.map((sig, i) => (
                <tr key={`${sig.index}-${i}`}>
                  <td style={{ padding: '8px 12px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                    {formatTimestamp(sig.time, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </td>
                  <td style={{ padding: '8px 12px', borderBottom: `1px solid ${colors.border}` }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 10px',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        backgroundColor: sig.type === 'BUY' ? `${colors.green}22` : `${colors.red}22`,
                        color: sig.type === 'BUY' ? colors.green : colors.red,
                      }}
                    >
                      {sig.type}
                    </span>
                  </td>
                  <td style={{ padding: '8px 12px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                    {currency.format(sig.price)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Live Alerts */}
      <div
        style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: 20,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 16 }}>
          Live Alerts
        </div>
        {recentLogs.length === 0 && (
          <div style={{ color: colors.textMuted, fontSize: 13 }}>No alerts</div>
        )}
        {recentLogs.map((log) => (
          <div
            key={log.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 0',
              borderBottom: `1px solid ${colors.border}`,
            }}
          >
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                flexShrink: 0,
                backgroundColor:
                  log.level === 'error' ? colors.red : log.level === 'warning' ? colors.amber : colors.blue,
              }}
            />
            <span style={{ fontSize: 12, color: colors.textMuted, flexShrink: 0 }}>
              {log.timestamp.toLocaleTimeString()}
            </span>
            <span style={{ fontSize: 13, color: colors.textPrimary }}>{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
