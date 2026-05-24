import React, { useState, useEffect, useCallback } from 'react'
import { TrendingUp, TrendingDown, Download, DollarSign, Target, BarChart3, Award, AlertTriangle } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { PageHeader } from '../../ui/PageHeader'
import { supabase } from '../../../lib/supabaseClient'

interface CryptoTrade {
  id: number
  created_at: string
  symbol: string
  side: 'BUY' | 'SELL' | 'ENTRY' | 'EXIT'
  qty: number
  entry_price: number
  exit_price: number
  trade_pnl: number
}

// Format P&L so negatives render as "-$250.00" not "$-250.00", and
// positives render with a leading "+". Used everywhere a P&L number is
// shown so the formatting stays consistent across the page.
const formatPnl = (n: number): string =>
  n >= 0 ? `+$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`

// Format quantities with the asset's base unit so the Qty column can
// never be visually confused with a USD price column.
const formatQty = (qty: number, symbol: string): string => {
  const decimals = symbol === 'BTC' ? 4 : symbol === 'ETH' ? 4 : 2
  return `${qty.toFixed(decimals)} ${symbol}`
}

const CryptoPerformanceView: React.FC = () => {
  const [liveTrades, setLiveTrades] = useState<CryptoTrade[]>([])
  const [equityCurve, setEquityCurve] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      
      // 1. Fetch trade history
      const { data: trades, error: tradesErr } = await supabase
        .from('paper_trades')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(100)

      if (tradesErr) throw tradesErr
      setLiveTrades(trades || [])

      // 2. Fetch equity snapshots for curve
      const { data: snapshots, error: snapErr } = await supabase
        .from('portfolio_snapshots')
        .select('snapshot_at, equity')
        .order('snapshot_at', { ascending: true })
        .limit(150)

      if (snapErr) throw snapErr
      
      const curve = (snapshots || []).map(s => ({
        date: new Date(s.snapshot_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        equity: Number(s.equity)
      }))
      setEquityCurve(curve)

    } catch (e) {
      console.error('Failed to fetch crypto performance data:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const totalPnl = liveTrades.reduce((sum, t) => sum + (Number(t.trade_pnl) || 0), 0)
  const wins = liveTrades.filter(t => (Number(t.trade_pnl) || 0) > 0).length
  const winRate = liveTrades.length > 0 ? ((wins / liveTrades.length) * 100).toFixed(1) : '0.0'
  const bestTrade = liveTrades.length > 0 ? Math.max(...liveTrades.map(t => Number(t.trade_pnl) || 0)) : 0
  const worstTrade = liveTrades.length > 0 ? Math.min(...liveTrades.map(t => Number(t.trade_pnl) || 0)) : 0

  const stats = [
    { label: 'Total Crypto P&L', value: formatPnl(totalPnl), icon: DollarSign, color: totalPnl >= 0 ? 'var(--green, #3fb950)' : 'var(--red, #f85149)' },
    { label: 'Win Rate', value: `${winRate}%`, icon: Target, color: 'var(--blue, #58a6ff)' },
    { label: 'Total Trades', value: `${liveTrades.length}`, icon: BarChart3, color: 'var(--text-primary, #e6edf3)' },
    { label: 'Best Trade', value: formatPnl(bestTrade), icon: Award, color: 'var(--green, #3fb950)' },
    { label: 'Worst Trade', value: formatPnl(worstTrade), icon: AlertTriangle, color: 'var(--red, #f85149)' },
  ]

  const handleExportCSV = () => {
    const header = 'ID,Date,Symbol,Side,Quantity,Entry Price,Exit Price,P&L,P&L %\n'
    const rows = liveTrades
      .map(t => {
        const entry = Number(t.entry_price) || 0
        const exit = Number(t.exit_price) || 0
        const returnPct = entry !== 0 ? ((exit - entry) / entry) * 100 : 0
        const dateStr = new Date(t.created_at).toISOString().split('T')[0]
        return `${t.id},${dateStr},${t.symbol},${t.side},${t.qty},${entry},${exit},${t.trade_pnl || 0},${returnPct.toFixed(2)}`
      })
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
        {loading ? (
          <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted, #8b949e)' }}>
            Loading equity curve data...
          </div>
        ) : equityCurve.length === 0 ? (
          <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted, #8b949e)', border: '1px dashed var(--border, #30363d)', borderRadius: '6px' }}>
            No equity snapshots found.
          </div>
        ) : (
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={equityCurve}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #30363d)" />
                <XAxis dataKey="date" stroke="var(--text-muted, #8b949e)" fontSize={12} />
                <YAxis
                  stroke="var(--text-muted, #8b949e)"
                  fontSize={12}
                  domain={['dataMin - 1000', 'dataMax + 1000']}
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
        )}
      </div>

      {/* Trade history */}
      <div style={cardStyle}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 16px 0' }}>Trade History</h2>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #8b949e)' }}>
            Loading historical trades...
          </div>
        ) : liveTrades.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #8b949e)', border: '1px dashed var(--border, #30363d)', borderRadius: '6px' }}>
            No historical trades found.
          </div>
        ) : (
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
                {liveTrades.map(trade => {
                  const entry = Number(trade.entry_price) || 0
                  const exit = Number(trade.exit_price) || 0
                  const pnl = Number(trade.trade_pnl) || 0
                  const pnlPercent = entry !== 0 ? ((exit - entry) / entry) * 100 : 0
                  const dateStr = new Date(trade.created_at).toLocaleDateString()
                  
                  return (
                    <tr key={trade.id} style={{ borderBottom: '1px solid var(--border, #30363d)' }}>
                      <td style={{ padding: '10px 12px' }}>{dateStr}</td>
                      <td style={{ padding: '10px 12px', fontWeight: 600 }}>{trade.symbol}</td>
                      <td style={{ padding: '10px 12px' }}>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            background: (trade.side === 'BUY' || trade.side === 'ENTRY') ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)',
                            color: (trade.side === 'BUY' || trade.side === 'ENTRY') ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                          }}
                        >
                          {trade.side}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>{formatQty(Number(trade.qty) || 0, trade.symbol)}</td>
                      <td style={{ padding: '10px 12px' }}>${entry.toLocaleString()}</td>
                      <td style={{ padding: '10px 12px' }}>${exit.toLocaleString()}</td>
                      <td
                        style={{
                          padding: '10px 12px',
                          fontWeight: 600,
                          color: pnl >= 0 ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                        }}
                      >
                        {formatPnl(pnl)}
                      </td>
                      <td
                        style={{
                          padding: '10px 12px',
                          color: pnlPercent >= 0 ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                        }}
                      >
                        {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default CryptoPerformanceView

