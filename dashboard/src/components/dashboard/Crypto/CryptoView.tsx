import React from 'react'
import { Bitcoin, TrendingUp, TrendingDown, Clock } from 'lucide-react'

export function CryptoView() {
  const assets = [
    { name: 'Bitcoin', symbol: 'BTC', price: 68450.20, change: +2.45, vol: '2.4B' },
    { name: 'Ethereum', symbol: 'ETH', price: 3450.15, change: -1.02, vol: '1.2B' },
    { name: 'Solana', symbol: 'SOL', price: 145.80, change: +5.12, vol: '850M' },
    { name: 'Cardano', symbol: 'ADA', price: 0.45, change: -2.30, vol: '120M' },
  ]

  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Crypto Monitor</h1>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}>
          <Clock size={14} style={{ marginRight: '6px' }} />
          Last update: Just now
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
        {assets.map((asset) => (
          <div key={asset.symbol} style={cardStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <div style={iconBoxStyle}><Bitcoin size={20} color="var(--blue)" /></div>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{asset.name}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{asset.symbol}/USD</div>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>${asset.price.toLocaleString()}</div>
                <div style={{ 
                  fontSize: '12px', 
                  fontWeight: 600, 
                  color: asset.change >= 0 ? 'var(--green)' : 'var(--red)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end'
                }}>
                  {asset.change >= 0 ? <TrendingUp size={12} style={{ marginRight: '4px' }} /> : <TrendingDown size={12} style={{ marginRight: '4px' }} />}
                  {Math.abs(asset.change)}%
                </div>
              </div>
            </div>
            
            <div style={{ height: '40px', background: 'var(--bg-tertiary)', borderRadius: '4px', marginBottom: '12px' }}>
              {/* Mini sparkline placeholder */}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              <span>24h Vol: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{asset.vol}</span></span>
              <span>High: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>${(asset.price * 1.05).toFixed(2)}</span></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const cardStyle = { padding: '20px', background: 'var(--bg-secondary)', borderRadius: '12px', border: '1px solid var(--border)' }
const iconBoxStyle = { width: '40px', height: '40px', background: 'var(--bg-tertiary)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '12px' }
