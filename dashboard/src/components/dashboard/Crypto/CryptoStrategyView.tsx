import React, { useState } from 'react'
import { Settings, Zap, Activity, ToggleLeft, ToggleRight } from 'lucide-react'
import { PageHeader } from '../../ui/PageHeader'

interface AssetToggle {
  symbol: string
  name: string
  enabled: boolean
}

const CryptoStrategyView: React.FC = () => {
  const [assets, setAssets] = useState<AssetToggle[]>([
    { symbol: 'BTC', name: 'Bitcoin', enabled: true },
    { symbol: 'ETH', name: 'Ethereum', enabled: true },
    { symbol: 'SOL', name: 'Solana', enabled: true },
    { symbol: 'ADA', name: 'Cardano', enabled: false },
  ])

  const [params, setParams] = useState({
    momentumPeriod: 14,
    rsiThreshold: 30,
    volumeFilter: 1000000,
    rebalanceInterval: 4,
  })

  const toggleAsset = (symbol: string) => {
    setAssets(prev => prev.map(a => (a.symbol === symbol ? { ...a, enabled: !a.enabled } : a)))
  }

  const cardStyle: React.CSSProperties = {
    background: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '12px',
    padding: '20px',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 12px',
    background: 'var(--bg-tertiary, #21262d)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '6px',
    color: 'var(--text-primary, #e6edf3)',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box',
  }

  return (
    <div style={{ padding: '24px', background: 'var(--bg-primary, #0d1117)', minHeight: '100vh', color: 'var(--text-primary, #e6edf3)' }}>
      <PageHeader
        title="Crypto strategy"
        subtitle="Momentum scanner"
        actions={
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 700,
              background: 'rgba(63,185,80,0.15)',
              color: 'var(--green, #3fb950)',
              border: '1px solid rgba(63,185,80,0.3)',
            }}
          >
            <Zap size={12} />
            24/7 ACTIVE
          </span>
        }
      />

      {/* Parameters grid */}
      <div style={{ ...cardStyle, marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Settings size={16} style={{ color: 'var(--blue, #58a6ff)' }} />
          <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>Parameters</h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', color: 'var(--text-muted, #8b949e)', fontSize: '12px', marginBottom: '6px' }}>
              Momentum Period
            </label>
            <input
              type="number"
              value={params.momentumPeriod}
              onChange={e => setParams(p => ({ ...p, momentumPeriod: parseInt(e.target.value) || 0 }))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ display: 'block', color: 'var(--text-muted, #8b949e)', fontSize: '12px', marginBottom: '6px' }}>
              RSI Threshold
            </label>
            <input
              type="number"
              value={params.rsiThreshold}
              onChange={e => setParams(p => ({ ...p, rsiThreshold: parseInt(e.target.value) || 0 }))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ display: 'block', color: 'var(--text-muted, #8b949e)', fontSize: '12px', marginBottom: '6px' }}>
              Volume Filter (USD)
            </label>
            <input
              type="number"
              value={params.volumeFilter}
              onChange={e => setParams(p => ({ ...p, volumeFilter: parseInt(e.target.value) || 0 }))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={{ display: 'block', color: 'var(--text-muted, #8b949e)', fontSize: '12px', marginBottom: '6px' }}>
              Rebalance Interval (hours)
            </label>
            <input
              type="number"
              value={params.rebalanceInterval}
              onChange={e => setParams(p => ({ ...p, rebalanceInterval: parseInt(e.target.value) || 0 }))}
              style={inputStyle}
            />
          </div>
        </div>
      </div>

      {/* Monitored assets */}
      <div style={{ ...cardStyle, marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Activity size={16} style={{ color: 'var(--blue, #58a6ff)' }} />
          <h2 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>Monitored Assets</h2>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {assets.map(asset => (
            <div
              key={asset.symbol}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px 16px',
                background: 'var(--bg-tertiary, #21262d)',
                borderRadius: '8px',
                border: '1px solid var(--border, #30363d)',
              }}
            >
              <div>
                <span style={{ fontWeight: 600, marginRight: '8px' }}>{asset.symbol}</span>
                <span style={{ color: 'var(--text-muted, #8b949e)', fontSize: '13px' }}>{asset.name}</span>
              </div>
              <button
                onClick={() => toggleAsset(asset.symbol)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {asset.enabled ? (
                  <ToggleRight size={28} style={{ color: 'var(--green, #3fb950)' }} />
                ) : (
                  <ToggleLeft size={28} style={{ color: 'var(--text-muted, #8b949e)' }} />
                )}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Strategy description */}
      <div style={cardStyle}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 12px 0' }}>Strategy Description</h2>
        <p style={{ color: 'var(--text-muted, #8b949e)', fontSize: '14px', lineHeight: 1.6, margin: 0 }}>
          The Crypto Momentum Scanner continuously monitors cryptocurrency markets 24/7, identifying momentum shifts
          using a combination of RSI divergence and volume analysis. When the momentum period detects a significant
          trend change above the RSI threshold with sufficient trading volume, the strategy generates buy or sell
          signals. The portfolio is automatically rebalanced at the configured interval to maintain optimal exposure
          across the monitored assets.
        </p>
      </div>
    </div>
  )
}

export default CryptoStrategyView
