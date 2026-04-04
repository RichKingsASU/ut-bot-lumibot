import React from 'react'

const SentimentView: React.FC = () => {
  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      <h2 style={{ margin: '0 0 24px', fontSize: 20, fontWeight: 600 }}>Market Sentiment</h2>

      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, padding: 40,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: 300,
      }}>
        <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>
          {/* Chart icon */}
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="20" x2="12" y2="10" />
            <line x1="18" y1="20" x2="18" y2="4" />
            <line x1="6" y1="20" x2="6" y2="16" />
          </svg>
        </div>
        <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-muted, #8b949e)', marginBottom: 8 }}>
          Market sentiment data not connected
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted, #8b949e)', opacity: 0.7, textAlign: 'center', maxWidth: 400 }}>
          Fear &amp; Greed Index, VIX, Put/Call ratio, and social sentiment require external data sources.
          Configure API connections in Settings to enable this view.
        </div>
      </div>
    </div>
  )
}

export default SentimentView
