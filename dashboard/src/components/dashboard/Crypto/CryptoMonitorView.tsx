import React, { useState, useEffect } from 'react'
import { Bitcoin, Clock, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

interface CryptoData {
  name: string
  symbol: string
  price: number
  change24h: number
  volume24h: number
  high24h: number
  low24h: number
}

const initialCryptos: CryptoData[] = [
  { name: 'Bitcoin', symbol: 'BTC', price: 67432.18, change24h: 2.34, volume24h: 28_400_000_000, high24h: 68100.0, low24h: 65800.0 },
  { name: 'Ethereum', symbol: 'ETH', price: 3521.47, change24h: -1.12, volume24h: 14_200_000_000, high24h: 3600.0, low24h: 3480.0 },
  { name: 'Solana', symbol: 'SOL', price: 142.85, change24h: 5.67, volume24h: 3_100_000_000, high24h: 148.0, low24h: 135.0 },
  { name: 'Cardano', symbol: 'ADA', price: 0.4523, change24h: -0.85, volume24h: 420_000_000, high24h: 0.462, low24h: 0.445 },
]

const CryptoMonitorView: React.FC = () => {
  const [cryptos, setCryptos] = useState<CryptoData[]>(initialCryptos)
  const [lastUpdate, setLastUpdate] = useState<string>('Just now')
  const [secondsSinceUpdate, setSecondsSinceUpdate] = useState(0)

  useEffect(() => {
    const priceInterval = setInterval(() => {
      setCryptos(prev =>
        prev.map(c => {
          const fluctuation = 1 + (Math.random() - 0.5) * 0.01
          const newPrice = parseFloat((c.price * fluctuation).toFixed(c.price < 1 ? 4 : 2))
          const newChange = parseFloat((c.change24h + (Math.random() - 0.5) * 0.2).toFixed(2))
          return { ...c, price: newPrice, change24h: newChange }
        })
      )
      setSecondsSinceUpdate(0)
      setLastUpdate('Just now')
    }, 30000)

    const tickInterval = setInterval(() => {
      setSecondsSinceUpdate(prev => {
        const next = prev + 1
        if (next < 5) setLastUpdate('Just now')
        else if (next < 60) setLastUpdate(`${next}s ago`)
        else setLastUpdate(`${Math.floor(next / 60)}m ago`)
        return next
      })
    }, 1000)

    return () => {
      clearInterval(priceInterval)
      clearInterval(tickInterval)
    }
  }, [])

  const formatVolume = (v: number) => {
    if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
    if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
    return `$${v.toLocaleString()}`
  }

  const formatPrice = (p: number) =>
    p < 1 ? `$${p.toFixed(4)}` : `$${p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  return (
    <div style={{ padding: '24px', background: 'var(--bg-primary, #0d1117)', minHeight: '100vh', color: 'var(--text-primary, #e6edf3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>Crypto Price Monitor</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted, #8b949e)', fontSize: '13px' }}>
          <RefreshCw size={14} style={{ animation: 'spin 2s linear infinite' }} />
          <Clock size={14} />
          <span>Last update: {lastUpdate}</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
        {cryptos.map(crypto => {
          const isPositive = crypto.change24h >= 0
          return (
            <div
              key={crypto.symbol}
              style={{
                background: 'var(--bg-secondary, #161b22)',
                border: '1px solid var(--border, #30363d)',
                borderRadius: '12px',
                padding: '20px',
                transition: 'border-color 0.2s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div
                    style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '50%',
                      background: 'var(--bg-tertiary, #21262d)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Bitcoin size={20} style={{ color: 'var(--amber, #e3b341)' }} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '16px' }}>{crypto.name}</div>
                    <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: '12px' }}>{crypto.symbol}/USD</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {isPositive ? (
                    <TrendingUp size={14} style={{ color: 'var(--green, #3fb950)' }} />
                  ) : (
                    <TrendingDown size={14} style={{ color: 'var(--red, #f85149)' }} />
                  )}
                  <span
                    style={{
                      color: isPositive ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                      fontSize: '14px',
                      fontWeight: 600,
                    }}
                  >
                    {isPositive ? '+' : ''}{crypto.change24h}%
                  </span>
                </div>
              </div>

              <div style={{ fontSize: '28px', fontWeight: 700, marginBottom: '12px' }}>
                {formatPrice(crypto.price)}
              </div>

              {/* Sparkline placeholder */}
              <div
                style={{
                  height: '40px',
                  background: 'var(--bg-tertiary, #21262d)',
                  borderRadius: '6px',
                  marginBottom: '16px',
                }}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                <div>
                  <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: '11px', marginBottom: '2px' }}>24h Volume</div>
                  <div style={{ fontSize: '13px', fontWeight: 500 }}>{formatVolume(crypto.volume24h)}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: '11px', marginBottom: '2px' }}>24h High</div>
                  <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--green, #3fb950)' }}>{formatPrice(crypto.high24h)}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: '11px', marginBottom: '2px' }}>24h Low</div>
                  <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--red, #f85149)' }}>{formatPrice(crypto.low24h)}</div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default CryptoMonitorView
