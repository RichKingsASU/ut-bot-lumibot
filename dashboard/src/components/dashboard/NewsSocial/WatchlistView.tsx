import React, { useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const WATCHLIST_DATA = [
  { ticker: 'IWM', mentionsPerHr: 142, change: 62, sentiment: 'bullish' as const },
  { ticker: 'SPY', mentionsPerHr: 318, change: 15, sentiment: 'bullish' as const },
  { ticker: 'QQQ', mentionsPerHr: 256, change: -8, sentiment: 'neutral' as const },
  { ticker: 'AAPL', mentionsPerHr: 189, change: 23, sentiment: 'bullish' as const },
  { ticker: 'TSLA', mentionsPerHr: 412, change: 85, sentiment: 'bearish' as const },
  { ticker: 'NVDA', mentionsPerHr: 534, change: 72, sentiment: 'bullish' as const },
  { ticker: 'AMD', mentionsPerHr: 167, change: 55, sentiment: 'bullish' as const },
  { ticker: 'META', mentionsPerHr: 98, change: -12, sentiment: 'neutral' as const },
  { ticker: 'AMZN', mentionsPerHr: 145, change: 34, sentiment: 'bullish' as const },
  { ticker: 'GOOGL', mentionsPerHr: 112, change: -5, sentiment: 'bearish' as const },
]

const MENTION_HISTORY = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i}:00`,
  IWM: Math.floor(80 + Math.random() * 100),
  TSLA: Math.floor(200 + Math.random() * 250),
  NVDA: Math.floor(300 + Math.random() * 300),
}))

const spikeAlerts = WATCHLIST_DATA.filter(d => d.change > 50)

const WatchlistView: React.FC = () => {
  const [selectedTicker, setSelectedTicker] = useState<string>('NVDA')

  const sentimentBadge = (s: 'bullish' | 'bearish' | 'neutral') => {
    const map: Record<string, { bg: string; text: string }> = {
      bullish: { bg: 'rgba(63,185,80,0.15)', text: '#3fb950' },
      bearish: { bg: 'rgba(248,81,73,0.15)', text: '#f85149' },
      neutral: { bg: 'rgba(139,148,158,0.15)', text: '#8b949e' },
    }
    const c = map[s]
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        textTransform: 'uppercase', backgroundColor: c.bg, color: c.text,
      }}>
        {s}
      </span>
    )
  }

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      <h2 style={{ margin: '0 0 24px', fontSize: 20, fontWeight: 600 }}>Social Watchlist</h2>

      {/* Spike Alerts */}
      {spikeAlerts.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(227, 179, 65, 0.08)',
          border: '1px solid rgba(227, 179, 65, 0.3)',
          borderRadius: 8, padding: 16, marginBottom: 20,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#e3b341', marginBottom: 8 }}>
            Spike Alerts (&gt;50% mention increase)
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {spikeAlerts.map(a => (
              <div key={a.ticker} style={{
                backgroundColor: 'rgba(227, 179, 65, 0.12)',
                border: '1px solid rgba(227, 179, 65, 0.25)',
                borderRadius: 6, padding: '6px 14px',
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span style={{ fontWeight: 700, color: '#e3b341', fontSize: 14 }}>{a.ticker}</span>
                <span style={{ fontSize: 12, color: '#e3b341' }}>+{a.change}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mention Velocity Table */}
      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, overflow: 'hidden', marginBottom: 20,
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--bg-tertiary, #21262d)' }}>
              {['Ticker', 'Mentions/hr', 'Change', 'Sentiment', 'Spike Alert'].map(h => (
                <th key={h} style={{
                  padding: '10px 16px', textAlign: 'left', fontWeight: 600,
                  color: 'var(--text-muted, #8b949e)', fontSize: 12, borderBottom: '1px solid var(--border, #30363d)',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {WATCHLIST_DATA.map(row => (
              <tr
                key={row.ticker}
                onClick={() => setSelectedTicker(row.ticker)}
                style={{
                  cursor: 'pointer',
                  backgroundColor: selectedTicker === row.ticker ? 'rgba(88,166,255,0.06)' : 'transparent',
                }}
              >
                <td style={{ padding: '10px 16px', fontWeight: 700, color: 'var(--blue, #58a6ff)', borderBottom: '1px solid var(--border, #30363d)' }}>
                  {row.ticker}
                </td>
                <td style={{ padding: '10px 16px', borderBottom: '1px solid var(--border, #30363d)' }}>
                  {row.mentionsPerHr}
                </td>
                <td style={{
                  padding: '10px 16px', borderBottom: '1px solid var(--border, #30363d)',
                  color: row.change >= 0 ? '#3fb950' : '#f85149', fontWeight: 600,
                }}>
                  {row.change >= 0 ? '+' : ''}{row.change}%
                </td>
                <td style={{ padding: '10px 16px', borderBottom: '1px solid var(--border, #30363d)' }}>
                  {sentimentBadge(row.sentiment)}
                </td>
                <td style={{ padding: '10px 16px', borderBottom: '1px solid var(--border, #30363d)' }}>
                  {row.change > 50 ? (
                    <span style={{ color: '#e3b341', fontWeight: 600, fontSize: 12 }}>SPIKE</span>
                  ) : (
                    <span style={{ color: 'var(--text-muted, #8b949e)', fontSize: 12 }}>Normal</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Historical Mention Chart */}
      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, padding: 24,
      }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>
          24-Hour Mention History
        </h3>
        <div style={{ width: '100%', height: 250 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={MENTION_HISTORY}>
              <XAxis dataKey="hour" tick={{ fill: '#8b949e', fontSize: 11 }} axisLine={{ stroke: '#30363d' }} tickLine={false} interval={3} />
              <YAxis tick={{ fill: '#8b949e', fontSize: 11 }} axisLine={{ stroke: '#30363d' }} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: 6, color: '#e6edf3' }}
                labelStyle={{ color: '#8b949e' }}
              />
              <Area type="monotone" dataKey="NVDA" stroke="#58a6ff" fill="rgba(88,166,255,0.1)" strokeWidth={2} />
              <Area type="monotone" dataKey="TSLA" stroke="#f85149" fill="rgba(248,81,73,0.1)" strokeWidth={2} />
              <Area type="monotone" dataKey="IWM" stroke="#3fb950" fill="rgba(63,185,80,0.1)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

export default WatchlistView
