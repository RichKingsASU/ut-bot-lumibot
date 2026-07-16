import React, { useState, useEffect } from 'react'
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Briefcase,
  Target,
  Activity,
  Wifi,
  WifiOff,
  LineChart as ChartIcon,
  Clock,
  AlertTriangle,
  Zap,
} from 'lucide-react'
import { useTradingContext } from '../../../context/TradingContext'
import { DataFreshness } from '../../DataFreshness'
import { useMetrics } from '../../../hooks/useMetrics'
import { EmergencyShutdown } from './EmergencyShutdown'
import { supabase } from '../../../lib/supabaseClient'
import { parseConfidence } from '../../../lib/confidence'
import { Link } from 'react-router-dom'
import { cn } from '../../../lib/utils'
import { BentoGrid, BentoTile } from '../../ui/BentoLayouts'
import { Badge } from '../../ui/Badge'
import { Skeleton } from '../../ui/Skeleton'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts'

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

// ─── Sub-Components ─────────────────────────────────────────────────────────

function TileHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("px-4 pt-4 pb-2 flex items-center justify-between", className)}>
      {children}
    </div>
  )
}

function TileTitle({ icon: Icon, children }: { icon?: React.ElementType; children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
      {Icon && <Icon size={13} className="opacity-60" />}
      {children}
    </h3>
  )
}

function StatBlock({
  label,
  value,
  subValue,
  trend,
  icon: Icon,
}: {
  label: string
  value: string
  subValue?: string
  trend?: 'up' | 'down' | 'neutral'
  icon?: React.ElementType
}) {
  const trendColor = trend === 'up' ? 'text-[#10b981]' : trend === 'down' ? 'text-[#ef4444]' : 'text-muted-foreground'
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1">
        {Icon && <Icon size={11} className="opacity-50" />}
        {label}
      </span>
      <span className={cn("text-xl font-bold tabular-nums font-mono tracking-tight leading-none", trendColor)}>
        {value}
      </span>
      {subValue && (
        <span className={cn("text-[10px] font-medium tabular-nums font-mono", trendColor)}>
          {subValue}
        </span>
      )}
    </div>
  )
}

function ConnectionDot({ online }: { online: boolean }) {
  return (
    <span
      className={cn(
        "w-2 h-2 rounded-full flex-shrink-0",
        online ? "bg-[#10b981] shadow-[0_0_6px_rgba(16,185,129,0.5)]" : "bg-[#ef4444]"
      )}
      role="status"
      aria-label={online ? "Connected" : "Disconnected"}
    />
  )
}

function StaleIndicator({ stale, lastUpdated }: { stale: boolean; lastUpdated?: Date | null }) {
  if (!stale) return null
  const ageLabel = (() => {
    if (!lastUpdated) return null
    const mins = Math.floor((Date.now() - lastUpdated.getTime()) / 60_000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    return `${Math.floor(mins / 60)}h ago`
  })()
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20" title="Alpaca broker disconnected — data may be stale">
      <AlertTriangle size={9} />
      STALE{ageLabel ? ` • ${ageLabel}` : ''}
    </span>
  )
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function OverviewView() {
  const {
    symbol,
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
  const [liveAgentSignals, setLiveAgentSignals] = useState<any[]>([])

  useEffect(() => {
    if (account) setLastUpdated(new Date())
  }, [account?.equity])

  // Fetch Regime + Equity Curve + Agent Signals
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

        // 3. Fetch live agent signals filtered by selected symbol
        const { data: agentSignalsData } = await supabase
          .from('agent_signals')
          .select('symbol, action, confidence, created_at, reasoning')
          .eq('symbol', symbol)
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
  }, [symbol])

  const { winRate: liveWinRate } = useMetrics()

  // ─── Derived Values ─────────────────────────────────────────────────────

  const equity = account ? parseFloat(account.equity) : 0
  const lastEquity = account ? parseFloat(account.last_equity) : 0
  const dayPnl = equity - lastEquity
  const dayPnlPct = lastEquity !== 0 ? (dayPnl / lastEquity) * 100 : 0
  const openPositions = positions.length
  const pnlTrend: 'up' | 'down' | 'neutral' = dayPnl > 0 ? 'up' : dayPnl < 0 ? 'down' : 'neutral'

  const connectionItems = [
    { name: 'Alpaca Broker', online: connected },
    { name: 'Supabase DB', online: true },
    { name: 'Bot Engine', online: botStatus.online },
  ]

  const regimeName = regimeData?.regime || 'QUIET'
  const regimeProb = regimeData?.probability ? (regimeData.probability * 100).toFixed(0) : null
  const regimeAge = regimeData?.detected_at
    ? (() => {
        const diffMs = Date.now() - new Date(regimeData.detected_at).getTime()
        const mins = Math.max(0, Math.floor(diffMs / 60000))
        if (mins < 60) return `${mins}m in state`
        const hrs = Math.floor(mins / 60)
        return `${hrs}h in state`
      })()
    : null

  const regimeColorMap: Record<string, string> = {
    BULL: '#10b981',
    BEAR: '#ef4444',
    VOLATILE: '#f59e0b',
    QUIET: '#3b82f6',
  }
  const regimeColor = regimeColorMap[regimeName] || '#8b949e'

  const recentLogs = [...logs].reverse().slice(0, 8)

  // ─── Loading State ──────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-8 w-32" />
        </div>
        <BentoGrid>
          {Array.from({ length: 8 }).map((_, i) => (
            <BentoTile key={i} colSpan={i < 2 ? 2 : 1} className="min-h-[180px]">
              <div className="p-4 space-y-3">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-8 w-40" />
                <Skeleton className="h-2 w-full" />
              </div>
            </BentoTile>
          ))}
        </BentoGrid>
      </div>
    )
  }

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="p-4 lg:p-6 h-full overflow-y-auto custom-scrollbar">

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">Command Board</h1>
          <p className="text-[11px] text-muted-foreground">Multi-agent status • Daily bars • Advisory only</p>
        </div>
        <div className="flex items-center gap-2">
          <EmergencyShutdown />
          <DataFreshness lastUpdated={lastUpdated} />
        </div>
      </div>

      {/* ── Bento Grid ──────────────────────────────────────────────────── */}
      <BentoGrid className="grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4 auto-rows-[minmax(160px,auto)] gap-3">

        {/* TILE: Portfolio Equity (2-col) */}
        <BentoTile colSpan={2} className="bg-card/60 backdrop-blur-sm border-border/40">
          <TileHeader>
            <TileTitle icon={DollarSign}>Portfolio</TileTitle>
            <StaleIndicator stale={!connected} lastUpdated={lastUpdated} />
          </TileHeader>
          <div className="px-4 pb-4 flex items-end justify-between gap-6">
            <StatBlock
              label="Total Equity"
              value={currency.format(equity)}
              icon={DollarSign}
            />
            <StatBlock
              label="Day P&L"
              value={`${dayPnl >= 0 ? '+' : ''}${currency.format(dayPnl)}`}
              subValue={`${dayPnlPct >= 0 ? '+' : ''}${dayPnlPct.toFixed(2)}%`}
              trend={pnlTrend}
              icon={pnlTrend === 'up' ? TrendingUp : TrendingDown}
            />
            <StatBlock
              label="Open Positions"
              value={String(openPositions)}
              icon={Briefcase}
            />
            <StatBlock
              label="Win Rate"
              value={liveWinRate == null ? '—' : `${liveWinRate}%`}
              icon={Target}
            />
          </div>
        </BentoTile>

        {/* TILE: HMM Regime */}
        <BentoTile colSpan={1} className="bg-card/60 backdrop-blur-sm border-border/40">
          <TileHeader>
            <TileTitle icon={Activity}>Market Regime</TileTitle>
          </TileHeader>
          <Link to="/admin/pipeline" className="px-4 pb-4 flex flex-col gap-2 flex-1 hover:bg-accent/5 transition-colors rounded-b-xl">
            <div className="flex items-center gap-2">
              <span
                className="text-2xl font-black tracking-tight"
                style={{ color: regimeColor }}
              >
                {regimeName}
              </span>
              {regimeProb && (
                <Badge variant="outline" className="text-[10px] font-mono tabular-nums">
                  {regimeProb}% conf
                </Badge>
              )}
            </div>
            {regimeAge && (
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <Clock size={10} />
                {regimeAge}
              </span>
            )}
            <p className="text-[9px] text-muted-foreground/60 mt-auto">
              HMM classifier • daily bars • click to inspect
            </p>
          </Link>
        </BentoTile>

        {/* TILE: System Health */}
        <BentoTile colSpan={1} className="bg-card/60 backdrop-blur-sm border-border/40">
          <TileHeader>
            <TileTitle icon={Wifi}>System Health</TileTitle>
          </TileHeader>
          <div className="px-4 pb-4 space-y-2.5 flex-1">
            {connectionItems.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between"
              >
                <span className="text-xs text-foreground font-medium">{item.name}</span>
                <div className="flex items-center gap-1.5">
                  <ConnectionDot online={item.online} />
                  <span className={cn(
                    "text-[10px] font-semibold tabular-nums",
                    item.online ? "text-[#10b981]" : "text-[#ef4444]"
                  )}>
                    {item.online ? 'OK' : 'DOWN'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </BentoTile>

        {/* TILE: Equity Curve (4-col) */}
        <BentoTile colSpan={4} rowSpan={2} className="bg-card/60 backdrop-blur-sm border-border/40">
          <TileHeader>
            <TileTitle icon={ChartIcon}>Equity Curve</TileTitle>
            <span className="text-[9px] text-muted-foreground font-mono tabular-nums">
              {equityData.length} snapshots
            </span>
          </TileHeader>
          <div className="px-4 pb-4 flex-1 min-h-0">
            {equityLoading ? (
              <div className="h-full flex items-center justify-center">
                <Skeleton className="h-full w-full rounded-lg" />
              </div>
            ) : equityData.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
                <ChartIcon size={32} className="opacity-20" />
                <span className="text-xs font-medium">No snapshot data yet</span>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equityData}>
                  <defs>
                    <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(217.2, 32.6%, 17.5%)" />
                  <XAxis
                    dataKey="snapshot_at"
                    tick={{ fill: 'hsl(215, 20.2%, 65.1%)', fontSize: 9, fontFamily: 'JetBrains Mono' }}
                    stroke="hsl(217.2, 32.6%, 17.5%)"
                    tickFormatter={(val) => {
                      try {
                        return new Date(val).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })
                      } catch {
                        return val
                      }
                    }}
                  />
                  <YAxis
                    tick={{ fill: 'hsl(215, 20.2%, 65.1%)', fontSize: 9, fontFamily: 'JetBrains Mono' }}
                    stroke="hsl(217.2, 32.6%, 17.5%)"
                    domain={['auto', 'auto']}
                    tickFormatter={(val) => currency.format(val).replace(/\.00$/, '')}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(224, 71.4%, 4.1%)',
                      border: '1px solid hsl(217.2, 32.6%, 17.5%)',
                      borderRadius: 8,
                      color: 'hsl(210, 20%, 98%)',
                      fontSize: 11,
                      fontFamily: 'JetBrains Mono',
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
                    stroke="#3b82f6"
                    strokeWidth={1.5}
                    fillOpacity={1}
                    fill="url(#colorEquity)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </BentoTile>

        {/* TILE: Recent Signals (2-col) */}
        <BentoTile colSpan={2} rowSpan={2} className="bg-card/60 backdrop-blur-sm border-border/40 overflow-hidden">
          <TileHeader>
            <TileTitle icon={Zap}>Agent Signals</TileTitle>
            <Badge variant="outline" className="text-[9px]">ADVISORY ONLY</Badge>
          </TileHeader>
          <div className="px-4 pb-4 flex-1 overflow-auto custom-scrollbar">
            <table className="w-full text-xs" role="grid">
              <thead>
                <tr className="border-b border-border">
                  {['Time', 'Sym', 'Action', 'Conf', 'Verdict'].map((h) => (
                    <th
                      key={h}
                      scope="col"
                      className="text-left px-2 py-1.5 text-[9px] font-bold text-muted-foreground uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {liveAgentSignals.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-muted-foreground text-center text-xs">
                      No signals yet
                    </td>
                  </tr>
                )}
                {liveAgentSignals.map((sig, i) => {
                  const actionColor = sig.action === 'BUY' ? 'text-[#10b981]' : sig.action === 'SELL' ? 'text-[#ef4444]' : 'text-muted-foreground'
                  const verdictColor = sig.verdict === 'ENTER' ? 'text-[#10b981]' : sig.verdict === 'AVOID' ? 'text-[#ef4444]' : 'text-muted-foreground'
                  return (
                    <tr key={i} className="hover:bg-accent/5 transition-colors">
                      <td className="px-2 py-2 text-muted-foreground font-mono tabular-nums">
                        {new Date(sig.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-2 py-2 font-bold text-foreground">
                        {sig.symbol}
                      </td>
                      <td className="px-2 py-2">
                        <span className={cn("font-bold", actionColor)}>{sig.action}</span>
                      </td>
                      <td className="px-2 py-2 font-mono tabular-nums text-foreground">
                        {(sig.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="px-2 py-2">
                        {sig.verdict ? (
                          <span className={cn("font-bold text-[10px]", verdictColor)}>
                            {sig.verdict}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </BentoTile>

        {/* TILE: Live Alerts (2-col) */}
        <BentoTile colSpan={2} rowSpan={2} className="bg-card/60 backdrop-blur-sm border-border/40 overflow-hidden">
          <TileHeader>
            <TileTitle icon={AlertTriangle}>Live Alerts</TileTitle>
            <span className="text-[9px] text-muted-foreground font-mono tabular-nums">
              {recentLogs.length} recent
            </span>
          </TileHeader>
          <div className="px-4 pb-4 flex-1 overflow-auto custom-scrollbar">
            {recentLogs.length === 0 && (
              <div className="text-muted-foreground text-xs py-4 text-center">No alerts</div>
            )}
            <div className="space-y-1">
              {recentLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start gap-2 py-1.5 text-xs"
                >
                  <span
                    className={cn(
                      "w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5",
                      log.level === 'error' ? 'bg-[#ef4444]' : log.level === 'warning' ? 'bg-[#f59e0b]' : 'bg-[#3b82f6]'
                    )}
                  />
                  <span className="text-[10px] text-muted-foreground font-mono tabular-nums flex-shrink-0 w-16">
                    {log.timestamp.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <span className="text-foreground leading-tight">{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </BentoTile>

      </BentoGrid>
    </div>
  )
}
