import React, { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Briefcase, Target, ShieldAlert, LineChart as ChartIcon } from 'lucide-react'
import { useTradingContext } from '../../../context/TradingContext'
import { DataFreshness } from '../../DataFreshness'
import { formatTimestamp } from '../../../lib/time'
import { PageHeader } from '../../ui/PageHeader'
import { useMetrics } from '../../../hooks/useMetrics'
import { EmergencyShutdown } from './EmergencyShutdown'
import { supabase } from '../../../lib/supabaseClient'
import { Link } from 'react-router-dom'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts'

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
  orange: '#f0883e',
}

const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

interface RegimeState {
  regime: string
  probability?: number
  detected_at?: string
}

interface PortfolioSnapshot {
  snapshot_at: string
  portfolio_value: number
  equity: number
}

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
  const [regimeData, setRegimeData] = useState<RegimeState | null>(null)
  const [equityData, setEquityData] = useState<PortfolioSnapshot[]>([])
  const [equityLoading, setEquityLoading] = useState(true)

  useEffect(() => {
    if (account) setLastUpdated(new Date())
  }, [account?.equity])

  // Fetch Regime + Equity Curve
  useEffect(() => {
    let cancelled = false

    async function fetchOverviewSupabaseData() {
      try {
        // 1. Fetch regime
        const { data: regimeRows } = await supabase
          .from('regime_states')
          .select('regime, probability, detected_at')
          .order('detected_at', { ascending: false })
          .limit(1)
          .maybeSingle()

        if (regimeRows && !cancelled) {
          setRegimeData({
            regime: String(regimeRows.regime || 'QUIET').toUpperCase(),
            probability: regimeRows.probability ? Number(regimeRows.probability) : undefined,
            detected_at: regimeRows.detected_at ? String(regimeRows.detected_at) : undefined,
          })
        }

        // 2. Fetch portfolio snapshots
        const { data: snapshots } = await supabase
          .from('portfolio_snapshots')
          .select('snapshot_at, portfolio_value, equity')
          .order('snapshot_at', { ascending: true })

        if (snapshots && !cancelled) {
          setEquityData(snapshots.map((s: any) => ({
            snapshot_at: s.snapshot_at || s.created_at || '',
            portfolio_value: Number(s.portfolio_value || s.equity || 0),
            equity: Number(s.equity || s.portfolio_value || 0),
          })))
        }

        // 3. Fetch live agent signals
        const { data: agentSignalsData } = await supabase
          .from('agent_signals')
          .select('symbol, action, confidence, created_at, reasoning')
          .order('created_at', { ascending: false })
          .limit(10)

        if (agentSignalsData && !cancelled) {
          setLiveAgentSignals(agentSignalsData.map((s: any) => {
            let verdict = null
            let bull = null
            let bear = null
            try {
              if (s.reasoning) {
                const r = JSON.parse(s.reasoning)
                verdict = r.verdict || r.decision || null
                bull = r.bull_score || r.bull || null
                bear = r.bear_score || r.bear || null
              }
            } catch {
              // Not JSON
            }
            return {
              symbol: s.symbol,
              action: s.action || 'HOLD',
              confidence: s.confidence != null ? Number(s.confidence) : 0.5,
              created_at: s.created_at || '',
              verdict,
              bull,
              bear,
            }
          }))
        }
      } catch (err) {
        console.error('Error fetching Overview Supabase data:', err)
      } finally {
        if (!cancelled) setEquityLoading(false)
      }
    }

    fetchOverviewSupabaseData()
    return () => {
      cancelled = true
    }
  }, [])

  const { winRate: liveWinRate } = useMetrics()

  const [liveAgentSignals, setLiveAgentSignals] = useState<any[]>([])

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

  const winRateDisplay = liveWinRate == null ? '—' : `${liveWinRate}%`

  const statCards = [
    { label: 'Total Equity', value: currency.format(equity), icon: DollarSign, color: colors.blue },
    {
      label: 'Day P&L',
      value: `${dayPnl >= 0 ? '+' : ''}${currency.format(dayPnl)} (${dayPnlPct >= 0 ? '+' : ''}${dayPnlPct.toFixed(2)}%)`,
      icon: TrendingUp,
      color: dayPnl >= 0 ? colors.green : colors.red,
    },
    { label: 'Open Positions', value: String(openPositions), icon: Briefcase, color: colors.amber },
    { label: 'Win Rate (all time)', value: winRateDisplay, icon: Target, color: colors.green },
  ]

  const recentLogs = [...logs].reverse().slice(0, 5)

  const connectionItems = [
    { name: 'Alpaca', online: connected },
    { name: 'Database', online: true },
    { name: 'Bot Engine', online: botStatus.online },
  ]

  // Regime styling configuration
  const getRegimeColor = (r: string) => {
    switch (r) {
      case 'BULL': return colors.green
      case 'BEAR': return colors.red
      case 'VOLATILE': return colors.orange
      case 'QUIET': return colors.blue
      default: return colors.textMuted
    }
  }

  const regimeName = regimeData?.regime || 'QUIET'
  const regimeColor = getRegimeColor(regimeName)
  const regimeProb = regimeData?.probability ? ` ${(regimeData.probability * 100).toFixed(0)}%` : ''
  const regimeAge = regimeData?.detected_at
    ? (() => {
        const diffMs = Date.now() - new Date(regimeData.detected_at).getTime()
        const mins = Math.max(0, Math.floor(diffMs / 60000))
        if (mins < 60) return `detected ${mins}m ago`
        const hrs = Math.floor(mins / 60)
        return `detected ${hrs}h ago`
      })()
    : 'detected recently'

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      <PageHeader
        title="Overview"
        subtitle="Live trading dashboard"
        actions={
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {/* Regime Badge */}
            <Link
              to="/admin/pipeline"
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                padding: '6px 12px',
                border: `1px solid ${regimeColor}`,
                backgroundColor: `${regimeColor}10`,
                borderRadius: 8,
                textDecoration: 'none',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ fontSize: 10, fontWeight: 700, color: regimeColor, letterSpacing: 0.5, textTransform: 'uppercase' }}>
                REGIME: {regimeName}{regimeProb}
              </div>
              <div style={{ fontSize: 9, color: colors.textMuted }}>
                {regimeAge}
              </div>
            </Link>
            <EmergencyShutdown />
            <DataFreshness lastUpdated={lastUpdated} />
          </div>
        }
      />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16, marginBottom: 24 }}>
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

        {/* HMM Regime Badge Card */}
        <Link
          to="/admin/pipeline"
          style={{
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${regimeColor}`,
            borderRadius: 8,
            padding: 20,
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            textDecoration: 'none',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = `${regimeColor}0a`
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = colors.bgSecondary
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 8,
              backgroundColor: `${regimeColor}18`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <TrendingUp size={22} color={regimeColor} />
          </div>
          <div>
            <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 4 }}>Market Regime</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: regimeColor }}>
              {regimeName}{regimeProb}
            </div>
            <div style={{ fontSize: 11, color: colors.textMuted }}>
              {regimeAge}
            </div>
          </div>
        </Link>
      </div>

      {/* Equity Curve Chart */}
      <div
        style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: 20,
          marginBottom: 24,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ChartIcon size={16} color={colors.blue} />
          Equity Curve (portfolio_snapshots)
        </div>
        <div style={{ height: 260, position: 'relative' }}>
          {equityLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted, fontSize: 13 }}>
              Loading portfolio snapshots...
            </div>
          ) : equityData.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted, gap: 10 }}>
              <ChartIcon size={32} style={{ opacity: 0.3 }} />
              <span style={{ fontSize: 13 }}>No snapshot data yet</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityData}>
                <defs>
                  <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={colors.blue} stopOpacity={0.2}/>
                    <stop offset="95%" stopColor={colors.blue} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.border} />
                <XAxis
                  dataKey="snapshot_at"
                  tick={{ fill: colors.textMuted, fontSize: 10 }}
                  stroke={colors.border}
                  tickFormatter={(val) => {
                    try {
                      return new Date(val).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })
                    } catch {
                      return val
                    }
                  }}
                />
                <YAxis
                  tick={{ fill: colors.textMuted, fontSize: 10 }}
                  stroke={colors.border}
                  domain={['auto', 'auto']}
                  tickFormatter={(val) => currency.format(val).replace(/\.00$/, '')}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: colors.bgTertiary,
                    border: `1px solid ${colors.border}`,
                    borderRadius: 6,
                    color: colors.textPrimary,
                    fontSize: 12,
                  }}
                  labelFormatter={(label) => {
                    try {
                      return new Date(label).toLocaleString()
                    } catch {
                      return label
                    }
                  }}
                  formatter={(value) => [currency.format(Number(value)), 'Equity']}
                />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke={colors.blue}
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorEquity)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
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
                {['Time', 'Symbol', 'Action', 'Confidence', 'Verdict'].map((h) => (
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
              {liveAgentSignals.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: 16, color: colors.textMuted, textAlign: 'center', fontSize: 13 }}>
                    No signals yet
                  </td>
                </tr>
              )}
              {liveAgentSignals.map((sig, i) => {
                const verdictColor =
                  sig.verdict === 'ENTER' ? colors.green :
                  sig.verdict === 'AVOID' ? colors.red :
                  colors.neutral
                return (
                  <tr key={i}>
                    <td style={{ padding: '8px 12px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                      {new Date(sig.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 700, color: colors.blue, borderBottom: `1px solid ${colors.border}` }}>
                      {sig.symbol}
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${colors.border}` }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 10px',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 600,
                          backgroundColor: sig.action === 'BUY' ? `${colors.green}22` : `${colors.red}22`,
                          color: sig.action === 'BUY' ? colors.green : colors.red,
                        }}
                      >
                        {sig.action}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                      {(sig.confidence * 100).toFixed(0)}%
                    </td>
                    <td style={{ padding: '8px 12px', borderBottom: `1px solid ${colors.border}` }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {sig.verdict ? (
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: 4,
                              fontSize: 11,
                              fontWeight: 600,
                              backgroundColor: `${verdictColor}22`,
                              color: verdictColor,
                              textTransform: 'uppercase',
                            }}
                          >
                            {sig.verdict}
                          </span>
                        ) : (
                          <span style={{ color: colors.textMuted }}>—</span>
                        )}
                        {(sig.bull !== null || sig.bear !== null) && (
                          <span style={{ fontSize: 11, color: colors.textMuted }}>
                            B{sig.bull ?? 0} / S{sig.bear ?? 0}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
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
