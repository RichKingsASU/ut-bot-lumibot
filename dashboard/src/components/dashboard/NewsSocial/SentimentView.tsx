import React from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const FEAR_GREED_VALUE = 62

const REDDIT_DATA = [
  { sub: 'r/wallstreetbets', bullish: 68, bearish: 32, posts: 1243 },
  { sub: 'r/stocks', bullish: 55, bearish: 45, posts: 487 },
  { sub: 'r/options', bullish: 42, bearish: 58, posts: 312 },
]

const TWITTER_DATA = [
  { day: 'Mon', mentions: 4200 },
  { day: 'Tue', mentions: 3800 },
  { day: 'Wed', mentions: 5100 },
  { day: 'Thu', mentions: 4700 },
  { day: 'Fri', mentions: 6300 },
  { day: 'Sat', mentions: 3200 },
  { day: 'Sun', mentions: 2900 },
]

const getFearGreedLabel = (value: number) => {
  if (value <= 20) return 'Extreme Fear'
  if (value <= 40) return 'Fear'
  if (value <= 60) return 'Neutral'
  if (value <= 80) return 'Greed'
  return 'Extreme Greed'
}

const getFearGreedColor = (value: number) => {
  if (value <= 20) return '#f85149'
  if (value <= 40) return '#f85149'
  if (value <= 60) return '#e3b341'
  if (value <= 80) return '#3fb950'
  return '#3fb950'
}

const SentimentView: React.FC = () => {
  const fgColor = getFearGreedColor(FEAR_GREED_VALUE)
  const fgLabel = getFearGreedLabel(FEAR_GREED_VALUE)
  const rotation = (FEAR_GREED_VALUE / 100) * 180 - 90

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      <h2 style={{ margin: '0 0 24px', fontSize: 20, fontWeight: 600 }}>Market Sentiment</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Fear & Greed Gauge */}
        <div style={{
          backgroundColor: 'var(--bg-secondary, #161b22)',
          border: '1px solid var(--border, #30363d)',
          borderRadius: 8, padding: 24,
          display: 'flex', flexDirection: 'column', alignItems: 'center',
        }}>
          <h3 style={{ margin: '0 0 20px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>Fear & Greed Index</h3>
          <div style={{ position: 'relative', width: 200, height: 110, marginBottom: 12 }}>
            {/* Semicircle background */}
            <div style={{
              position: 'absolute', width: 200, height: 100,
              borderRadius: '100px 100px 0 0',
              background: `conic-gradient(from 180deg at 50% 100%, #f85149 0deg, #e3b341 90deg, #3fb950 180deg)`,
              overflow: 'hidden',
            }} />
            {/* Inner cutout */}
            <div style={{
              position: 'absolute', left: 30, top: 30, width: 140, height: 70,
              borderRadius: '70px 70px 0 0',
              backgroundColor: 'var(--bg-secondary, #161b22)',
            }} />
            {/* Needle */}
            <div style={{
              position: 'absolute', bottom: 0, left: '50%',
              width: 2, height: 60,
              backgroundColor: 'var(--text-primary, #e6edf3)',
              transformOrigin: 'bottom center',
              transform: `translateX(-50%) rotate(${rotation}deg)`,
              transition: 'transform 0.5s ease',
            }} />
            {/* Center dot */}
            <div style={{
              position: 'absolute', bottom: -4, left: '50%', transform: 'translateX(-50%)',
              width: 10, height: 10, borderRadius: '50%',
              backgroundColor: 'var(--text-primary, #e6edf3)',
            }} />
          </div>
          <div style={{ fontSize: 36, fontWeight: 700, color: fgColor }}>{FEAR_GREED_VALUE}</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: fgColor, marginTop: 4 }}>{fgLabel}</div>
        </div>

        {/* Overall Summary */}
        <div style={{
          backgroundColor: 'var(--bg-secondary, #161b22)',
          border: '1px solid var(--border, #30363d)',
          borderRadius: 8, padding: 24,
        }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>Market Sentiment Summary</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[
              { label: 'Overall Bias', value: 'Moderately Bullish', color: '#3fb950' },
              { label: 'Social Volume', value: '↑ 18% vs avg', color: '#58a6ff' },
              { label: 'Put/Call Ratio', value: '0.72', color: '#3fb950' },
              { label: 'VIX Level', value: '14.2 (Low)', color: '#3fb950' },
              { label: 'Sector Rotation', value: 'Risk-On', color: '#e3b341' },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, color: 'var(--text-muted, #8b949e)' }}>{item.label}</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: item.color }}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Reddit Sentiment */}
      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, padding: 24, marginBottom: 20,
      }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>Reddit Sentiment</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {REDDIT_DATA.map(sub => (
            <div key={sub.sub} style={{
              backgroundColor: 'var(--bg-tertiary, #21262d)',
              borderRadius: 6, padding: 16,
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{sub.sub}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted, #8b949e)', marginBottom: 12 }}>{sub.posts} posts/day</div>
              {/* Ratio bar */}
              <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
                <div style={{ width: `${sub.bullish}%`, backgroundColor: '#3fb950' }} />
                <div style={{ width: `${sub.bearish}%`, backgroundColor: '#f85149' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span style={{ color: '#3fb950' }}>Bullish {sub.bullish}%</span>
                <span style={{ color: '#f85149' }}>Bearish {sub.bearish}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Twitter/X Mentions */}
      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, padding: 24,
      }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 500, color: 'var(--text-muted, #8b949e)' }}>X / Twitter Mentions (7-Day)</h3>
        <div style={{ width: '100%', height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={TWITTER_DATA}>
              <XAxis dataKey="day" tick={{ fill: '#8b949e', fontSize: 12 }} axisLine={{ stroke: '#30363d' }} tickLine={false} />
              <YAxis tick={{ fill: '#8b949e', fontSize: 12 }} axisLine={{ stroke: '#30363d' }} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: 6, color: '#e6edf3' }}
                labelStyle={{ color: '#8b949e' }}
              />
              <Bar dataKey="mentions" fill="#58a6ff" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

export default SentimentView
