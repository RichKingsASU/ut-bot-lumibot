import React from 'react'
import { Newspaper } from 'lucide-react'

const NewsFeedView: React.FC = () => {
  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <Newspaper size={22} color="var(--blue, #58a6ff)" />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>News Feed</h2>
      </div>

      <div style={{
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: '1px solid var(--border, #30363d)',
        borderRadius: 8, padding: 40,
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: 300,
      }}>
        <Newspaper size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
        <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-muted, #8b949e)', marginBottom: 8 }}>
          News feed unavailable
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted, #8b949e)', opacity: 0.7, textAlign: 'center', maxWidth: 400 }}>
          News data requires an Alpaca News API connection. Configure in Settings to enable real-time market news.
        </div>
      </div>
    </div>
  )
}

export default NewsFeedView
