import React, { useState } from 'react'
import { Newspaper, RefreshCw, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'

const MOCK_NEWS = [
  { id: 1, headline: 'Fed Signals Potential Rate Cut in Coming Months', source: 'Reuters', time: '2 hours ago', sentiment: 'bullish' as const, summary: 'Federal Reserve officials indicated they may begin lowering interest rates sooner than previously expected, citing cooling inflation data and signs of a slowing labor market. Markets rallied on the news as investors adjusted their rate expectations.' },
  { id: 2, headline: 'Tech Earnings Disappoint as AI Spending Surges', source: 'Bloomberg', time: '3 hours ago', sentiment: 'bearish' as const, summary: 'Several major tech companies reported earnings below analyst expectations as massive capital expenditures on AI infrastructure weighed on profit margins. Investors are growing concerned about the return on investment timeline for AI spending.' },
  { id: 3, headline: 'Oil Prices Surge on Middle East Supply Concerns', source: 'CNBC', time: '4 hours ago', sentiment: 'bearish' as const, summary: 'Crude oil prices jumped over 4% as geopolitical tensions in the Middle East raised fears of supply disruptions. Brent crude crossed $90 per barrel for the first time in months, adding inflationary pressure to the global economy.' },
  { id: 4, headline: 'NVIDIA Announces Next-Gen GPU Architecture', source: 'TechCrunch', time: '5 hours ago', sentiment: 'bullish' as const, summary: 'NVIDIA unveiled its next-generation GPU architecture promising 3x performance improvements for AI workloads. The announcement sent shares higher as analysts raised price targets across the board, citing continued dominance in the AI chip market.' },
  { id: 5, headline: 'Unemployment Claims Fall to 3-Month Low', source: 'WSJ', time: '6 hours ago', sentiment: 'bullish' as const, summary: 'Weekly jobless claims dropped to their lowest level in three months, suggesting the labor market remains resilient despite higher interest rates. The data supports the soft-landing narrative that has been driving market optimism.' },
  { id: 6, headline: 'China Manufacturing PMI Contracts for Third Month', source: 'Financial Times', time: '7 hours ago', sentiment: 'bearish' as const, summary: 'China\'s manufacturing sector continued to contract as weak domestic demand and property sector woes weigh on the world\'s second-largest economy. The data raises concerns about global growth prospects and commodity demand.' },
  { id: 7, headline: 'S&P 500 Hits New All-Time High on Broad Rally', source: 'MarketWatch', time: '8 hours ago', sentiment: 'bullish' as const, summary: 'The S&P 500 index closed at a record high as gains broadened beyond the mega-cap tech stocks that have led the rally. Financials, industrials, and healthcare sectors all posted strong gains, signaling improving market breadth.' },
  { id: 8, headline: 'Retail Sales Data Shows Consumer Spending Flat', source: 'AP News', time: '10 hours ago', sentiment: 'neutral' as const, summary: 'U.S. retail sales came in flat for the month, missing expectations of a modest increase. While not alarming, the data suggests consumers are becoming more cautious with their spending as pandemic-era savings continue to dwindle.' },
]

type SentimentFilter = 'all' | 'bullish' | 'bearish'

const NewsFeedView: React.FC = () => {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [filter, setFilter] = useState<SentimentFilter>('all')
  const [spinning, setSpinning] = useState(false)

  const toggleExpanded = (id: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const handleRefresh = () => {
    setSpinning(true)
    setTimeout(() => setSpinning(false), 1000)
  }

  const filteredNews = MOCK_NEWS.filter(item => {
    if (filter === 'all') return true
    return item.sentiment === filter
  })

  const sentimentBadge = (sentiment: 'bullish' | 'bearish' | 'neutral') => {
    const colors: Record<string, { bg: string; text: string }> = {
      bullish: { bg: 'rgba(63, 185, 80, 0.15)', text: '#3fb950' },
      bearish: { bg: 'rgba(248, 81, 73, 0.15)', text: '#f85149' },
      neutral: { bg: 'rgba(139, 148, 158, 0.15)', text: '#8b949e' },
    }
    const c = colors[sentiment]
    return (
      <span style={{
        padding: '2px 8px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'uppercase',
        backgroundColor: c.bg,
        color: c.text,
        letterSpacing: '0.5px',
      }}>
        {sentiment}
      </span>
    )
  }

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Newspaper size={22} color="var(--blue, #58a6ff)" />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>News Feed</h2>
        </div>
        <button
          onClick={handleRefresh}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 6,
            border: '1px solid var(--border, #30363d)',
            backgroundColor: 'var(--bg-secondary, #161b22)',
            color: 'var(--text-primary, #e6edf3)',
            cursor: 'pointer', fontSize: 13,
          }}
        >
          <RefreshCw size={14} style={{ transition: 'transform 0.3s', transform: spinning ? 'rotate(360deg)' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {(['all', 'bullish', 'bearish'] as SentimentFilter[]).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: '6px 16px', borderRadius: 6, fontSize: 13, fontWeight: 500,
              border: filter === f ? '1px solid var(--blue, #58a6ff)' : '1px solid var(--border, #30363d)',
              backgroundColor: filter === f ? 'rgba(88, 166, 255, 0.12)' : 'var(--bg-secondary, #161b22)',
              color: filter === f ? 'var(--blue, #58a6ff)' : 'var(--text-muted, #8b949e)',
              cursor: 'pointer', textTransform: 'capitalize',
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {/* News List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filteredNews.map(article => {
          const isExpanded = expandedIds.has(article.id)
          return (
            <div
              key={article.id}
              style={{
                backgroundColor: 'var(--bg-secondary, #161b22)',
                border: '1px solid var(--border, #30363d)',
                borderRadius: 8,
                overflow: 'hidden',
              }}
            >
              <div
                onClick={() => toggleExpanded(article.id)}
                style={{
                  padding: '14px 16px',
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  gap: 12,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary, #e6edf3)' }}>
                      {article.headline}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12 }}>
                    <span style={{ color: 'var(--blue, #58a6ff)', fontWeight: 500 }}>{article.source}</span>
                    <span style={{ color: 'var(--text-muted, #8b949e)' }}>{article.time}</span>
                    {sentimentBadge(article.sentiment)}
                  </div>
                </div>
                <div style={{ flexShrink: 0, color: 'var(--text-muted, #8b949e)' }}>
                  {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </div>
              </div>
              {isExpanded && (
                <div style={{
                  padding: '0 16px 14px 16px',
                  borderTop: '1px solid var(--border, #30363d)',
                }}>
                  <p style={{ margin: '12px 0 10px', fontSize: 13, lineHeight: 1.6, color: 'var(--text-muted, #8b949e)' }}>
                    {article.summary}
                  </p>
                  <a
                    href="#"
                    onClick={e => e.preventDefault()}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      fontSize: 12, color: 'var(--blue, #58a6ff)', textDecoration: 'none',
                    }}
                  >
                    Read full article <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default NewsFeedView
