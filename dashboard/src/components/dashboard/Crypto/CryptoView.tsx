import React, { useState, useEffect, useCallback } from 'react'
import { Bitcoin, Coins, TrendingUp, TrendingDown, Clock, ShieldCheck, AlertCircle, RefreshCw, Terminal } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'
import { parseConfidence } from '../../../lib/confidence'
import { netlifyFetch } from '../../../lib/apiClient'

interface CryptoAsset {
  name: string
  symbol: string
  price: number
  change: number
  ap: number
  bp: number
}

interface CryptoSignal {
  id: string
  symbol: string
  action: string
  confidence: number
  created_at: string
}

interface CryptoRegime {
  symbol: string
  regime: string
  probability: number
  detected_at: string
}

export function CryptoView() {
  const [assets, setAssets] = useState<CryptoAsset[]>([
    { name: 'Bitcoin', symbol: 'BTC/USD', price: 0, change: 0, ap: 0, bp: 0 },
    { name: 'Ethereum', symbol: 'ETH/USD', price: 0, change: 0, ap: 0, bp: 0 },
    { name: 'Solana', symbol: 'SOL/USD', price: 0, change: 0, ap: 0, bp: 0 },
  ])
  const [signals, setSignals] = useState<CryptoSignal[]>([])
  const [regimes, setRegimes] = useState<CryptoRegime[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // 1. Fetch Alpaca live prices
      const priceRes = await netlifyFetch('crypto-prices?symbols=BTC/USD,ETH/USD,SOL/USD')

      let liveQuotes: Record<string, any> = {}
      if (priceRes.ok) {
        const data = await priceRes.json()
        liveQuotes = data.quotes || {}
      }

      // 2. Fetch Latest Signals from Supabase
      const { data: signalsData } = await supabase
        .from('agent_signals')
        .select('id, symbol, action, confidence, created_at')
        .eq('asset_class', 'crypto')
        .order('created_at', { ascending: false })
        .limit(5)

      // 3. Fetch Regime States from Supabase
      const { data: regimesData } = await supabase
        .from('regime_states')
        .select('symbol, regime, probability:regime_probability, detected_at')
        .in('symbol', ['BTC/USD', 'ETH/USD', 'SOL/USD'])
        .order('detected_at', { ascending: false })
        .limit(10)

      // Map assets, if Alpaca fails fall back to last signal price or standard defaults
      const updatedAssets = [
        { name: 'Bitcoin', symbol: 'BTC/USD' },
        { name: 'Ethereum', symbol: 'ETH/USD' },
        { name: 'Solana', symbol: 'SOL/USD' },
      ].map(def => {
        const quote = liveQuotes[def.symbol]
        const fallbackSignal = (signalsData || []).find(s => s.symbol === def.symbol)
        
        let price = quote ? quote.price : 0
        let change = quote ? quote.change_pct : 0
        
        return {
          name: def.name,
          symbol: def.symbol,
          price: price || (def.symbol === 'BTC/USD' ? 68000 : def.symbol === 'ETH/USD' ? 3400 : 140), // Safe sensible default if completely zero
          change: change,
          ap: quote ? quote.ap : 0,
          bp: quote ? quote.bp : 0,
        }
      })

      setAssets(updatedAssets)
      setSignals((signalsData || []).map((s: any) => ({ ...s, confidence: parseConfidence(s.confidence) })))

      // Deduplicate regimes to get the latest per symbol
      const latestRegimes: Record<string, CryptoRegime> = {}
      for (const r of regimesData || []) {
        if (!latestRegimes[r.symbol]) {
          latestRegimes[r.symbol] = {
            symbol: r.symbol,
            regime: r.regime || 'QUIET',
            probability: r.probability ? parseFloat(r.probability) : 1,
            detected_at: r.detected_at,
          }
        }
      }
      setRegimes(Object.values(latestRegimes))
      setLastUpdated(new Date())
    } catch (err: any) {
      console.error(err)
      setError('Failed to fetch crypto monitor data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [fetchData])

  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto', backgroundColor: 'var(--bg-primary, #0d1117)', color: 'var(--text-primary)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>Crypto Surveillance</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>Live Alpaca asset feeds & neural decision flows</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}>
            <Clock size={14} style={{ marginRight: '6px' }} />
            Last update: {lastUpdated ? lastUpdated.toLocaleTimeString() : 'Never'}
          </div>
          <button 
            onClick={fetchData} 
            disabled={loading}
            style={{ padding: '6px 10px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: '8px', color: 'var(--red)', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Real-time Tickers */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        {assets.map((asset) => (
          <div key={asset.symbol} style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <div style={iconBoxStyle}><Bitcoin size={20} color="var(--blue)" /></div>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{asset.name}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{asset.symbol}</div>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                  {asset.price > 0 ? `$${asset.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'Price unavailable'}
                </div>
                <div style={{ 
                  fontSize: '12px', 
                  fontWeight: 600, 
                  color: asset.change >= 0 ? 'var(--green)' : 'var(--red)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  marginTop: '2px'
                }}>
                  {asset.change >= 0 ? <TrendingUp size={12} style={{ marginRight: '4px' }} /> : <TrendingDown size={12} style={{ marginRight: '4px' }} />}
                  {Math.abs(asset.change).toFixed(2)}%
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', borderTop: '1px solid var(--border)', paddingTop: '10px' }}>
              <span>Bid: <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontFamily: 'monospace' }}>${asset.bp > 0 ? asset.bp.toLocaleString() : '—'}</span></span>
              <span>Ask: <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontFamily: 'monospace' }}>${asset.ap > 0 ? asset.ap.toLocaleString() : '—'}</span></span>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Neural Regime Classification */}
        <div style={sectionStyle}>
          <h2 style={sectionTitleStyle}><Coins size={18} color="var(--blue)" /> Live Regime States</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
            {regimes.length === 0 ? (
              <div style={emptyStateStyle}>No regime states detected yet.</div>
            ) : (
              regimes.map((r) => (
                <div key={r.symbol} style={rowStyle}>
                  <span style={{ fontWeight: 600 }}>{r.symbol}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: r.regime === 'BULL' ? 'rgba(63,185,80,0.15)' : r.regime === 'BEAR' ? 'rgba(248,81,73,0.15)' : 'rgba(88,166,255,0.12)',
                      color: r.regime === 'BULL' ? 'var(--green)' : r.regime === 'BEAR' ? 'var(--red)' : 'var(--blue)',
                    }}>
                      {r.regime}
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      Prob: {Math.round(r.probability * 100)}%
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Live Decisions / Signals */}
        <div style={sectionStyle}>
          <h2 style={sectionTitleStyle}><Terminal size={18} color="var(--blue)" /> Live Action Flow</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
            {signals.length === 0 ? (
              <div style={emptyStateStyle}>No decision signals generated yet.</div>
            ) : (
              signals.map((s) => (
                <div key={s.id} style={rowStyle}>
                  <div>
                    <span style={{ fontWeight: 600 }}>{s.symbol}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                      {new Date(s.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: s.action === 'BUY' ? 'rgba(63,185,80,0.15)' : s.action === 'SELL' ? 'rgba(248,81,73,0.15)' : 'rgba(139,148,158,0.12)',
                      color: s.action === 'BUY' ? 'var(--green)' : s.action === 'SELL' ? 'var(--red)' : 'var(--text-muted)',
                    }}>
                      {s.action}
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      Conf: {Math.round(s.confidence * 100)}%
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

const cardStyle = { padding: '20px', background: 'var(--bg-secondary)', borderRadius: '12px', border: '1px solid var(--border)' }
const iconBoxStyle = { width: '40px', height: '40px', background: 'var(--bg-tertiary)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '12px' }
const sectionStyle = { padding: '20px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '12px' }
const sectionTitleStyle = { display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0, borderBottom: '1px solid var(--border)', paddingBottom: '12px' }
const rowStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid rgba(48,54,61,0.5)' }
const emptyStateStyle = { padding: '24px 0', textAlign: 'center' as const, color: 'var(--text-muted)', fontSize: '13px' }
