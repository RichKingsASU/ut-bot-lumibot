import React, { useState, useEffect } from 'react'
import { Bitcoin, Clock, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

interface CryptoQuote {
  symbol: string
  price: number
  change24h: number
}

const CRYPTO_SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD']

const CryptoMonitorView: React.FC = () => {
  const [quotes, setQuotes] = useState<CryptoQuote[]>([])
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchPrices = async () => {
    try {
      const res = await fetch(
        `/.netlify/functions/crypto-prices?symbols=${CRYPTO_SYMBOLS.map(encodeURIComponent).join(',')}`
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()

      const parsed = CRYPTO_SYMBOLS.map(sym => {
        const q = data.quotes?.[sym] || {}
        const midPrice = ((q.ap || 0) + (q.bp || 0)) / 2
        return { symbol: sym, price: midPrice, change24h: 0 }
      }).filter(q => q.price > 0)

      setQuotes(parsed)
      setLastUpdated(new Date())
      setError(null)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPrices()
    const interval = setInterval(fetchPrices, 30000)
    return () => clearInterval(interval)
  }, [])

  const formatPrice = (p: number) =>
    p < 1 ? `$${p.toFixed(4)}` : `$${p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  return (
    <div style={{ padding: '24px', background: 'var(--bg-primary, #0d1117)', minHeight: '100vh', color: 'var(--text-primary, #e6edf3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>Crypto — Monitor</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {lastUpdated && (
            <span style={{ fontSize: '13px', color: 'var(--text-muted, #8b949e)' }}>
              <Clock size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchPrices}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '6px 12px', fontSize: 12, color: 'var(--blue, #58a6ff)',
              background: 'none', border: '1px solid var(--border, #30363d)',
              borderRadius: 6, cursor: 'pointer',
            }}
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* 24/7 badge */}
      <div style={{
        marginBottom: 16, padding: 12,
        backgroundColor: 'rgba(168, 85, 247, 0.08)',
        border: '1px solid rgba(168, 85, 247, 0.2)',
        borderRadius: 8,
      }}>
        <span style={{ fontSize: 12, color: '#a855f7' }}>
          Crypto markets are open 24/7 — data streams continuously via Alpaca
        </span>
      </div>

      {error && (
        <div style={{
          marginBottom: 16, padding: 12,
          backgroundColor: 'rgba(248,81,73,0.08)',
          border: '1px solid rgba(248,81,73,0.2)',
          borderRadius: 8, fontSize: 12, color: 'var(--red, #f85149)',
        }}>
          Failed to load prices: {error}
        </div>
      )}

      {loading ? (
        <div style={{ fontSize: 13, color: 'var(--text-muted, #8b949e)' }}>Loading crypto prices from Alpaca...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {quotes.map(q => {
            const isPositive = q.change24h >= 0
            return (
              <div key={q.symbol} style={{
                background: 'var(--bg-secondary, #161b22)',
                border: '1px solid var(--border, #30363d)',
                borderRadius: 12, padding: 20,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 40, height: 40, borderRadius: '50%',
                      background: 'var(--bg-tertiary, #21262d)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <Bitcoin size={20} style={{ color: 'var(--amber, #e3b341)' }} />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{q.symbol}</div>
                      <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: 11 }}>Via Alpaca Crypto</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {isPositive ? (
                      <TrendingUp size={14} style={{ color: 'var(--green, #3fb950)' }} />
                    ) : (
                      <TrendingDown size={14} style={{ color: 'var(--red, #f85149)' }} />
                    )}
                    <span style={{
                      fontSize: 13, fontWeight: 600,
                      color: isPositive ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                    }}>
                      {isPositive ? '+' : ''}{q.change24h.toFixed(2)}%
                    </span>
                  </div>
                </div>

                <div style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>
                  {formatPrice(q.price)}
                </div>

                {/* Sparkline placeholder */}
                <div style={{
                  height: 40, background: 'var(--bg-tertiary, #21262d)',
                  borderRadius: 6, marginBottom: 12,
                }} />
              </div>
            )
          })}
          {quotes.length === 0 && !error && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', fontSize: 13, color: 'var(--text-muted, #8b949e)', padding: 32 }}>
              No price data available. Check Alpaca API connection.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default CryptoMonitorView
