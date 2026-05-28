import React, { useState, useEffect, useCallback } from 'react'
import { Activity, Shield, RefreshCw, AlertTriangle, Cpu } from 'lucide-react'

interface GreekData {
  symbol: string
  delta: number
  gamma: number
  theta: number
  vega: number
  iv_rank: number
  rvol: number
  trade_mode?: string
  snapshot_at?: string
  underlying_price?: number
}

export function OptionsView() {
  const [greeks, setGreeks] = useState<Record<string, GreekData>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)

  const fetchGreeks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const adminKey = import.meta.env.VITE_ADMIN_API_KEY || ''
      const res = await fetch('/.netlify/functions/get-greeks', {
        headers: { 'X-Admin-API-Key': adminKey }
      })

      if (!res.ok) throw new Error(`Netlify function status: ${res.status}`)

      const data = await res.json()
      setGreeks(data.symbols || {})
      setLastUpdated(data.last_updated || new Date().toISOString())
    } catch (e: any) {
      console.error(e)
      setError(e.message || 'Failed to fetch options greeks data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchGreeks()
    const interval = setInterval(fetchGreeks, 20000)
    return () => clearInterval(interval)
  }, [fetchGreeks])

  const symbolsList = Object.values(greeks)

  const getCircuitBreaker = (gamma: number) => {
    if (gamma > 0.08) return { label: 'BLOCK', color: 'var(--red)', bg: 'rgba(248,81,73,0.15)' }
    if (gamma > 0.05) return { label: 'REDUCE', color: '#e3b341', bg: 'rgba(227,179,65,0.15)' }
    return { label: 'CLEAR', color: 'var(--green)', bg: 'rgba(63,185,80,0.15)' }
  }

  const getIvColor = (rank: number) => {
    if (rank < 30) return 'var(--green)'
    if (rank <= 70) return '#e3b341'
    return 'var(--red)'
  }

  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto', backgroundColor: 'var(--bg-primary, #0d1117)', color: 'var(--text-primary)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>Greeks Surveillance</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>Real-time options risk profiles & circuit breakers</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {lastUpdated && (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Last sync: {new Date(lastUpdated).toLocaleTimeString()}
            </div>
          )}
          <button 
            onClick={fetchGreeks}
            disabled={loading}
            style={{ padding: '6px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Sync greeks
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: '8px', color: 'var(--red)', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {loading && symbolsList.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Retrieving real-time Greeks snapshots...
        </div>
      ) : symbolsList.length === 0 ? (
        <div style={{ padding: '32px', background: 'var(--bg-secondary)', border: '1.5px dashed var(--border)', borderRadius: '12px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <Shield size={36} style={{ margin: '0 auto 16px', color: 'var(--text-muted)', opacity: 0.5 }} />
          <p style={{ fontSize: '14px', lineHeight: 1.6, maxWidth: '500px', margin: '0 auto' }}>
            Greeks engine data will appear here once the options data worker has completed a full scan.
            Check <code style={{ color: 'var(--blue)' }}>/admin/health</code> to verify the options tmux session is running.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px' }}>
          {symbolsList.map((row) => {
            const cb = getCircuitBreaker(row.gamma)
            const ivColor = getIvColor(row.iv_rank)
            const isHighRvol = row.rvol > 2.5

            return (
              <div key={row.symbol} style={cardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <div>
                    <span style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>{row.symbol}</span>
                    {row.underlying_price && (
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '8px', fontFamily: 'monospace' }}>
                        Underlying: ${row.underlying_price.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <span style={{
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: cb.bg,
                    color: cb.color,
                    border: `1px solid ${cb.color}33`
                  }}>
                    {cb.label}
                  </span>
                </div>

                {/* Greeks Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '20px' }}>
                  {[
                    { label: 'Delta', value: row.delta },
                    { label: 'Gamma', value: row.gamma },
                    { label: 'Theta', value: row.theta },
                    { label: 'Vega', value: row.vega }
                  ].map(g => (
                    <div key={g.label} style={{ background: 'var(--bg-tertiary)', padding: '10px 6px', borderRadius: '6px', textAlign: 'center' }}>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>{g.label}</div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                        {g.value != null ? g.value.toFixed(4) : '—'}
                      </div>
                    </div>
                  ))}
                </div>

                {/* IV Rank */}
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                    <span>IV Rank</span>
                    <span style={{ color: ivColor, fontWeight: 700, fontFamily: 'monospace' }}>{Math.round(row.iv_rank)}%</span>
                  </div>
                  <div style={{ height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${row.iv_rank}%`, height: '100%', borderRadius: '3px', backgroundColor: ivColor }} />
                  </div>
                </div>

                {/* RVOL Indicator */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Relative Volume (RVOL)</span>
                  <span style={{
                    fontWeight: 700,
                    fontFamily: 'monospace',
                    color: isHighRvol ? 'var(--green)' : 'var(--red)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    {row.rvol != null ? `${row.rvol.toFixed(2)}x` : '—'}
                    {isHighRvol && <span style={{ fontSize: '10px', padding: '1px 4px', background: 'rgba(63,185,80,0.15)', borderRadius: '2px' }}>HIGH</span>}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const cardStyle = { padding: '20px', background: 'var(--bg-secondary)', borderRadius: '12px', border: '1px solid var(--border)' }
export default OptionsView
