import React, { useState, useEffect, useCallback } from 'react'
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'
import { RefreshCw, AlertTriangle, ShieldCheck, Activity } from 'lucide-react'

interface SnapshotData {
  date: string
  equity: number
  drawdown: number
}

export function AccountHealthView() {
  const [alpacaAcc, setAlpacaAcc] = useState<any>(null)
  const [snapshots, setSnapshots] = useState<SnapshotData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // 1. Fetch Alpaca Account
      const adminKey = import.meta.env.VITE_ADMIN_API_KEY || ''
      const accRes = await fetch('/.netlify/functions/alpaca-account', {
        headers: { 'X-Admin-API-Key': adminKey }
      })

      if (!accRes.ok) {
        throw new Error(`Alpaca API error: ${accRes.status}`)
      }

      const accData = await accRes.json()
      setAlpacaAcc(accData)

      // 2. Fetch Portfolio Snapshots
      const { data: snapshotsData, error: snapError } = await supabase
        .from('portfolio_snapshots')
        .select('snapshot_at, equity, portfolio_value:equity')
        .order('snapshot_at', { ascending: true })

      if (snapError) throw snapError

      // Compute drawdowns from snapshots or display equity curve
      let peak = 0
      const mappedSnapshots: SnapshotData[] = (snapshotsData || []).map(s => {
        const val = parseFloat(s.portfolio_value || s.equity || '0')
        if (val > peak) peak = val
        const drawdown = peak > 0 ? ((val - peak) / peak) * 100 : 0
        const dateObj = new Date(s.snapshot_at)
        return {
          date: `${dateObj.getMonth() + 1}/${dateObj.getDate()}`,
          equity: val,
          drawdown: Math.round(drawdown * 100) / 100
        }
      })

      setSnapshots(mappedSnapshots)
      setLastUpdated(new Date())
    } catch (err: any) {
      console.error(err)
      setError(err.message || 'Failed to sync account health metrics.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Computed fields
  const equity = alpacaAcc ? parseFloat(alpacaAcc.equity || '0') : 0
  const buyingPower = alpacaAcc ? parseFloat(alpacaAcc.buying_power || '0') : 0
  const portfolioValue = alpacaAcc ? parseFloat(alpacaAcc.portfolio_value || '0') : 0
  const daytradeCount = alpacaAcc ? parseInt(alpacaAcc.daytrade_count || alpacaAcc.day_trade_count || '0', 10) : 0
  const pdtStatus = alpacaAcc ? (alpacaAcc.pattern_day_trader || false) : false
  const initialMargin = alpacaAcc ? parseFloat(alpacaAcc.initial_margin || '0') : 0
  const maintenanceMargin = alpacaAcc ? parseFloat(alpacaAcc.maintenance_margin || '0') : 0

  const lastEquity = alpacaAcc ? parseFloat(alpacaAcc.last_equity || alpacaAcc.equity || '0') : 0
  const dailyPnL = equity - lastEquity
  const dailyTarget = 500
  const pnlPct = dailyTarget > 0 ? Math.min(Math.max((dailyPnL / dailyTarget) * 100, 0), 100) : 0

  const maxDrawdownLimit = 10
  // Compute max drawdown from historical snapshots
  const maxDrawdown = snapshots.length > 0 ? Math.min(...snapshots.map(s => s.drawdown)) : 0
  const riskScore = Math.min(100, Math.round((Math.abs(maxDrawdown) / maxDrawdownLimit) * 100))

  const getRiskColor = (score: number) => {
    if (score < 30) return 'var(--green)'
    if (score <= 60) return '#e3b341'
    return 'var(--red)'
  }

  const getRiskLabel = (score: number) => {
    if (score < 30) return 'Low Risk'
    if (score <= 60) return 'Moderate Risk'
    return 'High Risk'
  }

  const riskColor = getRiskColor(riskScore)

  const STAT_CARDS = [
    { label: 'Buying Power', value: `$${buyingPower.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, color: 'var(--text-primary)' },
    { label: 'Portfolio Value', value: `$${portfolioValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, color: 'var(--blue)' },
    { label: 'Daytrade Count', value: String(daytradeCount), color: 'var(--text-primary)' },
    { label: 'Initial Margin', value: `$${initialMargin.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, color: 'var(--text-primary)' },
    { label: 'Maintenance Margin', value: `$${maintenanceMargin.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, color: 'var(--text-primary)' },
    { label: 'PDT Status', value: pdtStatus ? 'FLAGGED' : 'CLEAR', color: pdtStatus ? 'var(--red)' : 'var(--green)' },
  ]

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <PageHeader title="Surveillance Core Health" subtitle="Live account risk & liquidity matrix" />
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            onClick={fetchData} 
            disabled={loading}
            style={{ padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Sync Account
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: '8px', color: 'var(--red)', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {loading && !alpacaAcc ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Syncing risk and account metrics...
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 20, marginBottom: 20 }}>
            {/* Risk Score Gauge */}
            <div style={{
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 8, padding: 24,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12, fontWeight: 500 }}>
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
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>/100</div>
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: riskColor, marginTop: 12 }}>
                {getRiskLabel(riskScore)}
              </div>
            </div>

            {/* Stat Cards Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {STAT_CARDS.map(card => (
                <div key={card.label} style={{
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  borderRadius: 8, padding: 18,
                  display: 'flex', flexDirection: 'column', justifyContent: 'center',
                }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 500 }}>
                    {card.label}
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: card.color, fontFamily: 'monospace' }}>
                    {card.value}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Daily P&L Progress */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 8, padding: 20, marginBottom: 20,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 2 }}>Daily P&L Progress</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Target: ${dailyTarget.toLocaleString()}</div>
              </div>
              <div style={{
                fontSize: 22, fontWeight: 700,
                color: dailyPnL >= 0 ? 'var(--green)' : 'var(--red)',
                fontFamily: 'monospace'
              }}>
                {dailyPnL >= 0 ? '+' : ''}${dailyPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
            <div style={{
              height: 12, borderRadius: 6,
              backgroundColor: 'var(--bg-tertiary)',
              overflow: 'hidden',
              position: 'relative',
            }}>
              <div style={{
                width: `${pnlPct}%`,
                height: '100%',
                borderRadius: 6,
                backgroundColor: dailyPnL >= 0 ? 'var(--green)' : 'var(--red)',
                transition: 'width 0.5s ease',
              }} />
              <div style={{
                position: 'absolute', top: -2, right: 0, width: 2, height: 16,
                backgroundColor: 'var(--text-muted)',
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
              <span>$0</span>
              <span>{Math.round(pnlPct)}% of target</span>
              <span>${dailyTarget.toLocaleString()}</span>
            </div>
          </div>

          {/* Equity Curve with Drawdown Overlay */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 8, padding: 24,
          }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted)' }}>
              Surveillance Equity Curve & Drawdown Profile
            </h3>
            {snapshots.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '40px 0', textAlign: 'center' }}>
                No snapshots history found in database. Equity curve will populate as strategy snapshots ingest.
              </div>
            ) : (
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={snapshots}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: '#8b949e', fontSize: 11 }}
                      axisLine={{ stroke: '#30363d' }}
                      tickLine={false}
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
        </>
      )}
    </div>
  )
}

export default AccountHealthView
