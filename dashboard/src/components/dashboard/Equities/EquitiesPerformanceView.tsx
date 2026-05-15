import React, { useState, useEffect, useCallback, useMemo } from 'react'
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
import { PageHeader } from '../../ui/PageHeader'
import { useMetrics } from '../../../hooks/useMetrics'
import { supabase } from '../../../lib/supabaseClient'

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

export default function EquitiesPerformanceView() {
  const { loading: contextLoading } = useTradingContext()
  const [liveTrades, setLiveTrades] = useState<any[]>([])
  const [equityCurve, setEquityCurve] = useState<any[]>([])
  const [fetching, setFetching] = useState(true)

  const {
    winRate: liveWinRate,
    totalPnl: liveTotalPnl,
    totalTrades: liveTotalTrades,
    maxDrawdown: liveMaxDrawdown,
  } = useMetrics()

  const fetchData = useCallback(async () => {
    setFetching(true)
    try {
      // 1. Fetch trade history
      const { data: trades } = await supabase
        .from('paper_trades')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(50);
      setLiveTrades(trades || []);

      // 2. Fetch equity snapshots for curve
      const { data: snapshots } = await supabase
        .from('portfolio_snapshots')
        .select('created_at, equity')
        .order('created_at', { ascending: true })
        .limit(100);
      
      const curve = (snapshots || []).map(s => ({
        date: new Date(s.created_at).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' }),
        equity: Number(s.equity)
      }));
      setEquityCurve(curve);
    } catch (e) {
      console.error('Failed to fetch performance data:', e);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const statCards = useMemo(() => {
    const fmtCurrency = (v: number | null | undefined) =>
      v == null || !Number.isFinite(v) ? '—' : currency.format(v)
    const fmtPct = (v: number | null | undefined) =>
      v == null || !Number.isFinite(v) ? '—' : `${(v * 100).toFixed(1)}%`
    const pnlColor =
      liveTotalPnl == null
        ? colors.textPrimary
        : liveTotalPnl >= 0
          ? colors.green
          : colors.red
    const ddColor = liveMaxDrawdown == null ? colors.textPrimary : colors.red
    return [
      { label: 'Total P&L', value: fmtCurrency(liveTotalPnl), color: pnlColor },
      { label: 'Win Rate', value: fmtPct(liveWinRate), color: colors.blue },
      { label: 'Total Trades', value: liveTotalTrades ?? '—', color: colors.textPrimary },
      { label: 'Max Drawdown', value: fmtCurrency(liveMaxDrawdown), color: ddColor },
    ]
  }, [liveTotalPnl, liveWinRate, liveTotalTrades, liveMaxDrawdown])

  const handleExportCSV = useCallback(() => {
    const rows = liveTrades ?? []
    const headers = ['date', 'symbol', 'side', 'entry_price', 'exit_price', 'trade_pnl', 'return_pct']
    const escape = (v: unknown) => {
      const s = v == null ? '' : String(v)
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }
    const lines = [headers.join(',')]
    for (const t of rows) {
      const entry = Number(t?.entry_price)
      const exit = Number(t?.exit_price)
      const ret = Number.isFinite(entry) && entry !== 0 && Number.isFinite(exit)
        ? ((exit - entry) / entry) * 100
        : 0
      lines.push([
        t?.created_at ?? '',
        t?.symbol ?? '',
        t?.side ?? '',
        entry,
        exit,
        t?.trade_pnl ?? '',
        ret.toFixed(4),
      ].map(escape).join(','))
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `equities-performance-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [liveTrades])

  if (contextLoading || fetching) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted }}>
        Loading live performance data...
      </div>
    )
  }

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      <PageHeader
        title="Equities performance"
        subtitle="Paper account results"
        actions={
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
        }
      />

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
            <LineChart data={equityCurve.length > 0 ? equityCurve : [{ date: 'No Data', equity: 100000 }]}>
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
          Trade History (Last 50)
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
            {liveTrades.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: 40, textAlign: 'center', color: colors.textMuted }}>
                  No historical trades found.
                </td>
              </tr>
            ) : liveTrades.map((trade, i) => {
              const returnPct = trade.entry_price ? ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100 : 0;
              return (
                <tr key={i}>
                  <td style={{ padding: '10px 16px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                    {new Date(trade.created_at).toLocaleDateString()}
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
                    {currency.format(trade.entry_price)}
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 13, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                    {currency.format(trade.exit_price)}
                  </td>
                  <td
                    style={{
                      padding: '10px 16px',
                      fontSize: 13,
                      fontWeight: 500,
                      color: trade.trade_pnl >= 0 ? colors.green : colors.red,
                      borderBottom: `1px solid ${colors.border}`,
                    }}
                  >
                    {trade.trade_pnl >= 0 ? '+' : ''}
                    {currency.format(trade.trade_pnl)}
                  </td>
                  <td
                    style={{
                      padding: '10px 16px',
                      fontSize: 13,
                      fontWeight: 500,
                      color: returnPct >= 0 ? colors.green : colors.red,
                      borderBottom: `1px solid ${colors.border}`,
                    }}
                  >
                    {returnPct >= 0 ? '+' : ''}
                    {returnPct.toFixed(2)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
