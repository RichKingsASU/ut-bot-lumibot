import React, { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, Briefcase, Target, ShieldAlert, LineChart as ChartIcon } from 'lucide-react'
import { useTradingContext } from '../../../context/TradingContext'
import { DataFreshness } from '../../DataFreshness'
import { formatTimestamp } from '../../../lib/time'
import { PageHeader } from '../../ui/PageHeader'
import { useMetrics } from '../../../hooks/useMetrics'
import { EmergencyShutdown } from './EmergencyShutdown'
import { supabase } from '../../../lib/supabaseClient'
import { parseConfidence } from '../../../lib/confidence'
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
          .select('regime, probability:regime_probability, detected_at')
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
          .select('snapshot_at, portfolio_value:equity, equity')
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
              confidence: parseConfidence(s.confidence),
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
    <div className="p-6 h-full overflow-y-auto bg-space bg-grid custom-scrollbar relative">
      <PageHeader
        title="Overview"
        subtitle="Live trading dashboard"
        actions={
          <div className="flex items-center gap-3">
            {/* Regime Badge */}
            <Link
              to="/admin/pipeline"
              style={{
                borderColor: regimeColor,
                backgroundColor: `${regimeColor}10`,
              }}
              className="flex flex-col items-end px-3 py-1.5 border rounded-xl hover:bg-white/[0.02] transition-smooth cursor-pointer shadow-sm"
            >
              <div style={{ color: regimeColor }} className="text-[10px] font-bold tracking-wider uppercase leading-none">
                REGIME: {regimeName}{regimeProb}
              </div>
              <div className="text-[9px] text-secondary mt-0.5 leading-none">
                {regimeAge}
              </div>
            </Link>
            <EmergencyShutdown />
            <DataFreshness lastUpdated={lastUpdated} />
          </div>
        }
      />
      
      {/* Statistics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <div
              key={card.label}
              className="bg-surface-1/40 hover:bg-surface-1/65 border border-border-muted/50 hover:border-vibrant/40 rounded-2xl p-5 flex items-center gap-4 transition-smooth backdrop-blur-md shadow-premium"
            >
              <div
                style={{
                  backgroundColor: `${card.color}15`,
                }}
                className="w-11 h-11 rounded-xl flex items-center justify-center shadow-inner"
              >
                <Icon size={20} color={card.color} />
              </div>
              <div>
                <div className="text-xs text-secondary mb-0.5 tracking-tight font-medium">{card.label}</div>
                <div className="text-lg font-bold text-primary tracking-tight leading-tight">{card.value}</div>
              </div>
            </div>
          )
        })}

        {/* HMM Regime Badge Card */}
        <Link
          to="/admin/pipeline"
          style={{
            borderColor: regimeColor,
            backgroundColor: 'rgba(24, 24, 27, 0.4)',
          }}
          className="hover:bg-surface-1/65 border rounded-2xl p-5 flex items-center gap-4 transition-smooth backdrop-blur-md shadow-premium cursor-pointer"
        >
          <div
            style={{
              backgroundColor: `${regimeColor}15`,
            }}
            className="w-11 h-11 rounded-xl flex items-center justify-center shadow-inner"
          >
            <TrendingUp size={20} color={regimeColor} />
          </div>
          <div>
            <div className="text-xs text-secondary mb-0.5 tracking-tight font-medium">Market Regime</div>
            <div style={{ color: regimeColor }} className="text-lg font-extrabold tracking-tight leading-tight">
              {regimeName}{regimeProb}
            </div>
            <div className="text-[10px] text-secondary mt-0.5 leading-none">
              {regimeAge}
            </div>
          </div>
        </Link>
      </div>

      {/* Equity Curve Chart */}
      <div
        className="bg-surface-1/40 border border-border-muted/50 rounded-2xl p-5 mb-6 backdrop-blur-md shadow-premium"
      >
        <div className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
          <ChartIcon size={16} className="text-blue-400" />
          Equity Curve (portfolio_snapshots)
        </div>
        <div className="h-[280px] relative">
          {equityLoading ? (
            <div className="flex items-center justify-center h-full text-secondary text-xs">
              Loading portfolio snapshots...
            </div>
          ) : equityData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-secondary gap-2">
              <ChartIcon size={32} className="opacity-20" />
              <span className="text-xs font-medium">No snapshot data yet</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityData}>
                <defs>
                  <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={colors.blue} stopOpacity={0.25}/>
                    <stop offset="95%" stopColor={colors.blue} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis
                  dataKey="snapshot_at"
                  tick={{ fill: colors.textMuted, fontSize: 9, fontWeight: 500 }}
                  stroke="rgba(255,255,255,0.08)"
                  tickFormatter={(val) => {
                    try {
                      return new Date(val).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })
                    } catch {
                      return val
                    }
                  }}
                />
                <YAxis
                  tick={{ fill: colors.textMuted, fontSize: 9, fontWeight: 500 }}
                  stroke="rgba(255,255,255,0.08)"
                  domain={['auto', 'auto']}
                  tickFormatter={(val) => currency.format(val).replace(/\.00$/, '')}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(24, 24, 27, 0.95)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 12,
                    color: colors.textPrimary,
                    fontSize: 12,
                    boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                    backdropFilter: 'blur(8px)',
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
      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 mb-6">
        {/* Connection Health */}
        <div
          className="bg-surface-1/40 border border-border-muted/50 rounded-2xl p-5 backdrop-blur-md shadow-premium"
        >
          <div className="text-sm font-bold text-primary mb-4">
            Connection Health
          </div>
          <div className="space-y-1">
            {connectionItems.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between py-2.5 border-b border-border-muted/20 last:border-b-0"
              >
                <span className="text-primary text-xs font-medium">{item.name}</span>
                <div className="flex items-center gap-2">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      item.online ? 'bg-green-400 animate-pulse' : 'bg-red-400'
                    }`}
                  />
                  <span className={`text-xs font-semibold ${item.online ? 'text-green-400' : 'text-red-400'}`}>
                    {item.online ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Signals */}
        <div
          className="bg-surface-1/40 border border-border-muted/50 rounded-2xl p-5 backdrop-blur-md shadow-premium overflow-x-auto custom-scrollbar"
        >
          <div className="text-sm font-bold text-primary mb-4">
            Recent Signals
          </div>
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-border-muted/30">
                {['Time', 'Symbol', 'Action', 'Confidence', 'Verdict'].map((h) => (
                  <th
                    key={h}
                    className="text-left px-3 py-2 text-[10px] font-bold text-secondary uppercase tracking-wider pb-2.5"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-muted/10">
              {liveAgentSignals.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-secondary text-center text-xs">
                    No signals yet
                  </td>
                </tr>
              )}
              {liveAgentSignals.map((sig, i) => {
                const verdictColor =
                  sig.verdict === 'ENTER' ? colors.green :
                  sig.verdict === 'AVOID' ? colors.red :
                  colors.textMuted
                return (
                  <tr key={i} className="hover:bg-white/[0.01] transition-smooth">
                    <td className="px-3 py-3 text-xs text-primary font-medium">
                      {new Date(sig.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="px-3 py-3 text-xs font-extrabold text-blue-400">
                      {sig.symbol}
                    </td>
                    <td className="px-3 py-3">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-lg text-[10px] font-bold border ${
                          sig.action === 'BUY' 
                            ? 'bg-green-500/10 text-green-400 border-green-500/20' 
                            : 'bg-red-500/10 text-red-400 border-red-500/20'
                        }`}
                      >
                        {sig.action}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-xs text-primary font-mono">
                      {(sig.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        {sig.verdict ? (
                          <span
                            className="inline-block px-2 py-0.5 rounded-lg text-[9px] font-extrabold border uppercase"
                            style={{
                              backgroundColor: `${verdictColor}18`,
                              color: verdictColor,
                              borderColor: `${verdictColor}33`,
                            }}
                          >
                            {sig.verdict}
                          </span>
                        ) : (
                          <span className="text-secondary">—</span>
                        )}
                        {(sig.bull !== null || sig.bear !== null) && (
                          <span className="text-[10px] text-secondary font-mono">
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
        className="bg-surface-1/40 border border-border-muted/50 rounded-2xl p-5 backdrop-blur-md shadow-premium mb-6"
      >
        <div className="text-sm font-bold text-primary mb-4">
          Live Alerts
        </div>
        {recentLogs.length === 0 && (
          <div className="text-secondary text-xs">No alerts</div>
        )}
        <div className="divide-y divide-border-muted/10">
          {recentLogs.map((log) => (
            <div
              key={log.id}
              className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0"
            >
              <div
                className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  log.level === 'error' ? 'bg-red-400 animate-pulse' : log.level === 'warning' ? 'bg-amber-400' : 'bg-blue-400'
                }`}
              />
              <span className="text-[10px] text-secondary font-semibold font-mono flex-shrink-0">
                {log.timestamp.toLocaleTimeString()}
              </span>
              <span className="text-xs text-primary font-medium">{log.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
