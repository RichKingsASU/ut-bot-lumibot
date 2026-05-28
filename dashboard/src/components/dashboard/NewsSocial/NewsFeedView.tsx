import React, { useEffect, useState } from 'react'
import { Newspaper, Calendar, Globe, BarChart2 } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'

interface Article {
  id: number
  title: string
  url: string
  source: string
  published_at: string
  summary: string
  sentiment_score: number | null
  sentiment_label?: string
  asset_class: string
}

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
  neutral: '#8b949e',
}

const NewsFeedView: React.FC = () => {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState({
    countLast24h: 0,
    averageScore: 0,
    dominantLabel: 'neutral'
  })

  useEffect(() => {
    let cancelled = false

    async function fetchNews() {
      try {
        setLoading(true)
        const { data, error } = await supabase
          .from('news_articles')
          .select('id, title, url, source, published_at, summary, sentiment_score, asset_class')
          .order('published_at', { ascending: false })
          .limit(20)

        if (cancelled) return
        if (error) throw error

        if (data) {
          const mapped: Article[] = data.map((item: any) => {
            const score = item.sentiment_score != null ? Number(item.sentiment_score) : null
            let label = 'neutral'
            if (score != null) {
              if (score > 0.15) label = 'positive'
              else if (score < -0.15) label = 'negative'
            }
            return {
              id: item.id,
              title: item.title,
              url: item.url,
              source: item.source || 'Unknown',
              published_at: item.published_at,
              summary: item.summary || '',
              sentiment_score: score,
              sentiment_label: label,
              asset_class: item.asset_class || 'equities'
            }
          })

          setArticles(mapped)

          // Compute summary stats
          const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000
          const last24h = mapped.filter(a => new Date(a.published_at).getTime() > oneDayAgo)
          
          let sumScore = 0
          let scoredCount = 0
          let posCount = 0
          let negCount = 0
          let neuCount = 0

          for (const a of mapped) {
            if (a.sentiment_score != null) {
              sumScore += a.sentiment_score
              scoredCount++
              if (a.sentiment_label === 'positive') posCount++
              else if (a.sentiment_label === 'negative') negCount++
              else neuCount++
            }
          }

          const avg = scoredCount > 0 ? sumScore / scoredCount : 0
          let dominant = 'neutral'
          if (posCount > negCount && posCount > neuCount) dominant = 'positive'
          else if (negCount > posCount && negCount > neuCount) dominant = 'negative'

          setSummary({
            countLast24h: last24h.length,
            averageScore: avg,
            dominantLabel: dominant
          })
        }
      } catch (err) {
        console.error('Error fetching FinBERT news articles:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchNews()
    return () => {
      cancelled = true
    }
  }, [])

  const getSentimentStyles = (label: string | undefined) => {
    switch (label) {
      case 'positive':
        return { backgroundColor: 'rgba(63, 185, 80, 0.15)', color: colors.green }
      case 'negative':
        return { backgroundColor: 'rgba(248, 81, 73, 0.15)', color: colors.red }
      default:
        return { backgroundColor: 'rgba(139, 148, 158, 0.15)', color: colors.neutral }
    }
  }

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts)
      return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    } catch {
      return ts
    }
  }

  return (
    <div style={{ padding: 24, backgroundColor: colors.bgPrimary, minHeight: '100%', color: colors.textPrimary }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <Newspaper size={22} color={colors.blue} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Market News & Sentiment Feed</h2>
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: colors.textMuted }}>
          Loading real-time news feed...
        </div>
      ) : articles.length === 0 ? (
        <div style={{
          backgroundColor: colors.bgSecondary,
          border: `1px solid ${colors.border}`,
          borderRadius: 8, padding: 40,
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', minHeight: 300,
        }}>
          <Newspaper size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
          <div style={{ fontSize: 16, fontWeight: 500, color: colors.textMuted, marginBottom: 8 }}>
            No news data yet — FinBERT collector may not be running. Check System Health.
          </div>
          <div style={{ fontSize: 13, color: colors.textMuted, opacity: 0.7, textAlign: 'center', maxWidth: 400 }}>
            Ensure your market data collectors and FinBERT services are online.
          </div>
        </div>
      ) : (
        <>
          {/* Summary bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 24,
            padding: '16px 20px',
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            marginBottom: 20,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Calendar size={16} color={colors.blue} />
              <span style={{ fontSize: 13, color: colors.textMuted }}>
                📰 <strong>{summary.countLast24h}</strong> articles in last 24h
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <BarChart2 size={16} color={colors.blue} />
              <span style={{ fontSize: 13, color: colors.textMuted }}>
                Avg sentiment: <strong style={{ color: summary.averageScore >= 0 ? colors.green : colors.red }}>
                  {summary.averageScore >= 0 ? '+' : ''}{summary.averageScore.toFixed(2)}
                </strong>{' '}
                (<span style={{ textTransform: 'capitalize', color: summary.dominantLabel === 'positive' ? colors.green : summary.dominantLabel === 'negative' ? colors.red : colors.neutral }}>
                  {summary.dominantLabel}
                </span>)
              </span>
            </div>
          </div>

          {/* News Table */}
          <div style={{
            backgroundColor: colors.bgSecondary,
            border: `1px solid ${colors.border}`,
            borderRadius: 8,
            overflow: 'hidden',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ backgroundColor: colors.bgTertiary }}>
                  {['Time', 'Source', 'Headline', 'Sentiment', 'Asset Class'].map((h) => (
                    <th key={h} style={{
                      padding: '12px 16px',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: colors.textMuted,
                      fontSize: 11,
                      borderBottom: `1px solid ${colors.border}`,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px'
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {articles.map((art) => {
                  const badge = getSentimentStyles(art.sentiment_label)
                  return (
                    <tr key={art.id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                      <td style={{ padding: '14px 16px', color: colors.textMuted, whiteSpace: 'nowrap' }}>
                        {formatTime(art.published_at)}
                      </td>
                      <td style={{ padding: '14px 16px', fontWeight: 500 }}>
                        {art.source}
                      </td>
                      <td style={{ padding: '14px 16px', maxWidth: 400 }}>
                        <a href={art.url} target="_blank" rel="noopener noreferrer" style={{
                          color: colors.textPrimary,
                          textDecoration: 'none',
                          fontWeight: 500,
                          lineHeight: 1.4,
                        }}
                        onMouseOver={e => e.currentTarget.style.color = colors.blue}
                        onMouseOut={e => e.currentTarget.style.color = colors.textPrimary}>
                          {art.title}
                        </a>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        {art.sentiment_score != null ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: 4,
                              fontSize: 11,
                              fontWeight: 600,
                              ...badge
                            }}>
                              {art.sentiment_label?.toUpperCase()}
                            </span>
                            <span style={{ fontSize: 11, color: art.sentiment_score >= 0 ? colors.green : colors.red }}>
                              {art.sentiment_score >= 0 ? '+' : ''}{art.sentiment_score.toFixed(2)}
                            </span>
                          </div>
                        ) : (
                          <span style={{ color: colors.textMuted }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px', textTransform: 'capitalize', color: colors.textMuted }}>
                        {art.asset_class}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

export default NewsFeedView

