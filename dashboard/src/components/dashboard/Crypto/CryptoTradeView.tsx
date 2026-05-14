import React, { useState, useEffect, useMemo } from 'react'
import { PageHeader } from '../../ui/PageHeader'
import { PriceChart, type PriceChartBar } from '../../ui/PriceChart'

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
  purple: '#a855f7',
}

const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

const SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD']

interface BarData {
  t: string
  o: number
  h: number
  l: number
  c: number
  v: number
}

export default function CryptoTradeView() {
  const [symbol, setSymbol] = useState('BTC/USD')
  const [bars, setBars] = useState<BarData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchBars = async () => {
      setLoading(true)
      try {
        const res = await fetch(
          `/.netlify/functions/crypto-bars?symbol=${encodeURIComponent(symbol)}&timeframe=1Min&limit=200`
        )
        if (res.ok) {
          const data = await res.json()
          const barData = data.bars?.[symbol] || []
          setBars(barData)
        }
      } catch (e) {
        console.error('Failed to fetch crypto bars:', e)
      } finally {
        setLoading(false)
      }
    }

    fetchBars()
    const interval = setInterval(fetchBars, 30000)
    return () => clearInterval(interval)
  }, [symbol])

  const latestBar = bars.length > 0 ? bars[bars.length - 1] : null

  const chartBars: PriceChartBar[] = useMemo(
    () =>
      bars.map((b) => ({
        time: Math.floor(new Date(b.t).getTime() / 1000),
        open: b.o,
        high: b.h,
        low: b.l,
        close: b.c,
      })),
    [bars],
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: colors.bgPrimary }}>
      <div style={{ padding: '20px 24px 0' }}>
        <PageHeader title="Crypto trading" subtitle="BTC · ETH · SOL" />
      </div>
      {/* Symbol Tabs */}
      <div style={{
        display: 'flex', gap: 0,
        borderBottom: `1px solid ${colors.border}`,
        backgroundColor: colors.bgSecondary,
        flexShrink: 0,
      }}>
        {SYMBOLS.map((sym) => (
          <button
            key={sym}
            onClick={() => setSymbol(sym)}
            style={{
              padding: '12px 28px', fontSize: 13, fontWeight: 600,
              color: sym === symbol ? colors.purple : colors.textMuted,
              backgroundColor: 'transparent', border: 'none',
              borderBottom: sym === symbol ? `2px solid ${colors.purple}` : '2px solid transparent',
              cursor: 'pointer', transition: 'color 0.15s',
            }}
          >
            {sym}
          </button>
        ))}
      </div>

      {/* 24/7 Banner */}
      <div style={{
        margin: '12px 16px 0',
        padding: 10,
        backgroundColor: 'rgba(168, 85, 247, 0.08)',
        border: '1px solid rgba(168, 85, 247, 0.2)',
        borderRadius: 6, flexShrink: 0,
      }}>
        <span style={{ fontSize: 12, color: colors.purple }}>
          Crypto runs 24/7 — no market hours restriction
        </span>
      </div>

      {/* Main content */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Chart Area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{
            flex: 1,
            backgroundColor: colors.bgSecondary, margin: 16, marginRight: 0,
            borderRadius: 8, border: `1px solid ${colors.border}`,
            padding: 12,
            minHeight: 320,
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ fontSize: 12, color: colors.textMuted, fontWeight: 600 }}>
                {symbol} · 1Min
              </div>
              {latestBar && (
                <div style={{ fontSize: 12, color: colors.textMuted }}>
                  Latest: {currency.format(latestBar.c)} | Bars: {bars.length}
                </div>
              )}
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              {loading && bars.length === 0 ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: colors.textMuted, fontSize: 14 }}>
                  Loading chart data...
                </div>
              ) : (
                <PriceChart bars={chartBars} symbol={symbol} height={320} />
              )}
            </div>
          </div>

          {/* Recent Bars Log */}
          <div style={{
            height: 220, flexShrink: 0,
            margin: '0 16px 16px 16px', marginRight: 0,
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 8, overflow: 'hidden',
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{
              padding: '12px 16px', fontSize: 13, fontWeight: 600,
              color: colors.textPrimary,
              borderBottom: `1px solid ${colors.border}`, flexShrink: 0,
            }}>
              Recent Bars
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Time', 'Open', 'Close', 'Volume'].map(h => (
                      <th key={h} style={{
                        position: 'sticky', top: 0, textAlign: 'left',
                        padding: '8px 12px', fontSize: 11, color: colors.textMuted,
                        borderBottom: `1px solid ${colors.border}`,
                        backgroundColor: colors.bgSecondary,
                        textTransform: 'uppercase', letterSpacing: 0.5,
                      }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bars.length === 0 && (
                    <tr>
                      <td colSpan={4} style={{ padding: 16, color: colors.textMuted, textAlign: 'center', fontSize: 13 }}>
                        No bars loaded yet
                      </td>
                    </tr>
                  )}
                  {[...bars].reverse().slice(0, 20).map((bar, i) => (
                    <tr key={i}>
                      <td style={{ padding: '6px 12px', fontSize: 12, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                        {new Date(bar.t).toLocaleTimeString()}
                      </td>
                      <td style={{ padding: '6px 12px', fontSize: 12, color: colors.textPrimary, borderBottom: `1px solid ${colors.border}` }}>
                        {currency.format(bar.o)}
                      </td>
                      <td style={{
                        padding: '6px 12px', fontSize: 12, borderBottom: `1px solid ${colors.border}`,
                        color: bar.c >= bar.o ? colors.green : colors.red,
                      }}>
                        {currency.format(bar.c)}
                      </td>
                      <td style={{ padding: '6px 12px', fontSize: 12, color: colors.textMuted, borderBottom: `1px solid ${colors.border}` }}>
                        {Number(bar.v ?? 0).toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Position Panel */}
        <div style={{
          width: 280, flexShrink: 0,
          backgroundColor: colors.bgSecondary,
          padding: 20, margin: '16px 16px 16px 16px',
          borderRadius: 8, border: `1px solid ${colors.border}`,
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 20 }}>
            Position
          </div>
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: colors.textMuted, fontSize: 13,
          }}>
            No active crypto positions
          </div>
        </div>
      </div>
    </div>
  )
}
