import React from 'react'
import { Settings, Save, Radio, SlidersHorizontal, AlertTriangle, CheckCircle, ToggleLeft, ToggleRight } from 'lucide-react'
import { API } from '../../../lib/api'

// ── Types ────────────────────────────────────────────────────────────────────

interface BotConfig {
  active_symbol: string
  trade_spy: string
  trade_iwm: string
  trade_qqq: string
  trade_btc: string
  trade_eth: string
  atr_period: string
  atr_mult: string
  rsi_period: string
  rsi_oversold: string
  rsi_overbought: string
  paper_mode: string
  [key: string]: string
}

const DEFAULT_CONFIG: BotConfig = {
  active_symbol: 'IWM',
  trade_spy: 'false',
  trade_iwm: 'true',
  trade_qqq: 'false',
  trade_btc: 'false',
  trade_eth: 'false',
  atr_period: '10',
  atr_mult: '1.0',
  rsi_period: '14',
  rsi_oversold: '30',
  rsi_overbought: '70',
  paper_mode: 'true',
}

const INSTRUMENTS = [
  { key: 'SPY', tradeKey: 'trade_spy', label: 'SPY', isCrypto: false },
  { key: 'IWM', tradeKey: 'trade_iwm', label: 'IWM', isCrypto: false },
  { key: 'QQQ', tradeKey: 'trade_qqq', label: 'QQQ', isCrypto: false },
  { key: 'BTC', tradeKey: 'trade_btc', label: 'BTC', isCrypto: true },
  { key: 'ETH', tradeKey: 'trade_eth', label: 'ETH', isCrypto: true },
]

const SIGNAL_PARAMS = [
  { key: 'atr_period', label: 'ATR Period', min: 1, max: 100, step: 1 },
  { key: 'atr_mult', label: 'ATR Mult', min: 0.1, max: 10, step: 0.1 },
  { key: 'rsi_period', label: 'RSI Period', min: 2, max: 100, step: 1 },
  { key: 'rsi_oversold', label: 'RSI Oversold', min: 0, max: 100, step: 1 },
  { key: 'rsi_overbought', label: 'RSI Overbought', min: 0, max: 100, step: 1 },
]

// ── Main Component ───────────────────────────────────────────────────────────

export function SettingsView() {
  const [config, setConfig] = React.useState<BotConfig>({ ...DEFAULT_CONFIG })
  const [savedConfig, setSavedConfig] = React.useState<BotConfig>({ ...DEFAULT_CONFIG })
  const [updatedAt, setUpdatedAt] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [toast, setToast] = React.useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // ── Fetch config on mount ──────────────────────────────────────────
  const fetchConfig = React.useCallback(async () => {
    try {
      const res = await fetch(API.botConfig())
      if (!res.ok) throw new Error('Failed to fetch config')
      const data = await res.json()
      if (data.config) {
        const merged = { ...DEFAULT_CONFIG, ...data.config }
        setConfig(merged)
        setSavedConfig(merged)
        setUpdatedAt(data.updated_at || null)
      }
    } catch (err: any) {
      console.error('Failed to load config:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { fetchConfig() }, [fetchConfig])

  // ── Toast auto-dismiss ─────────────────────────────────────────────
  React.useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

  // ── Dirty tracking ─────────────────────────────────────────────────
  const isDirty = (key: string) => config[key] !== savedConfig[key]
  const hasAnyDirty = Object.keys(config).some(k => isDirty(k))

  // ── Instrument selection ───────────────────────────────────────────
  const selectInstrument = (symbol: string) => {
    const updated = { ...config, active_symbol: symbol }
    for (const inst of INSTRUMENTS) {
      updated[inst.tradeKey] = inst.key === symbol ? 'true' : 'false'
    }
    setConfig(updated)
  }

  // ── Save ───────────────────────────────────────────────────────────
  const handleSave = async () => {
    setSaving(true)
    try {
      const changedKeys = Object.keys(config).filter(k => config[k] !== savedConfig[k])
      for (const key of changedKeys) {
        const res = await fetch(API.botConfig(), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value: config[key] }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.error || `Failed to save ${key}`)
        }
      }
      setToast({ type: 'success', message: 'Settings saved' })
      await fetchConfig()
    } catch (err: any) {
      setToast({ type: 'error', message: `Save failed: ${err.message}` })
    } finally {
      setSaving(false)
    }
  }

  // ── Paper mode toggle ──────────────────────────────────────────────
  const paperMode = config.paper_mode === 'true'
  const togglePaperMode = () => {
    setConfig(prev => ({ ...prev, paper_mode: prev.paper_mode === 'true' ? 'false' : 'true' }))
  }

  const isCryptoSelected = config.active_symbol === 'BTC' || config.active_symbol === 'ETH'

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--text-muted)' }}>
        Loading configuration...
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
          padding: '12px 24px',
          background: toast.type === 'success' ? '#089981' : '#f23645',
          color: '#fff', fontWeight: 600, fontSize: '14px',
          textAlign: 'center',
          animation: 'slideDown 0.2s ease-out',
        }}>
          {toast.type === 'success' ? <CheckCircle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} /> : <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />}
          {toast.message}
        </div>
      )}

      <div style={{ flex: 1, overflow: 'auto', padding: '24px', maxWidth: '900px', margin: '0 auto', width: '100%' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' }}>
          <Settings size={22} style={{ color: '#2962ff' }} />
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Bot Configuration
            </h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '4px', fontSize: '13px', margin: 0 }}>
              K2 ATR Trailing Stop — signal parameters and active instrument
            </p>
          </div>
        </div>

        {/* ── Section 1: Active Instrument ─────────────────────────────── */}
        <SectionCard icon={Radio} title="Active Instrument">
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {INSTRUMENTS.map(inst => {
              const isActive = config.active_symbol === inst.key
              return (
                <button
                  key={inst.key}
                  onClick={() => selectInstrument(inst.key)}
                  style={{
                    padding: '12px 24px',
                    background: isActive ? '#2962ff' : 'var(--bg-primary)',
                    color: isActive ? '#fff' : 'var(--text-muted)',
                    border: isActive ? '2px solid #2962ff' : '2px solid var(--border)',
                    borderRadius: '8px',
                    fontWeight: 700,
                    fontSize: '15px',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    minWidth: '80px',
                    outline: isDirty('active_symbol') && isActive ? '2px solid #f0b429' : 'none',
                    outlineOffset: '2px',
                  }}
                >
                  {inst.label}
                </button>
              )
            })}
          </div>
          {isCryptoSelected && (
            <div style={{
              marginTop: '16px', padding: '12px 16px',
              background: 'rgba(240, 180, 41, 0.1)',
              border: '1px solid rgba(240, 180, 41, 0.3)',
              borderRadius: '6px',
              color: '#f0b429',
              fontSize: '13px',
              fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: '8px',
            }}>
              <AlertTriangle size={16} />
              Crypto trades 24/7 — EOD flatten will not apply.
            </div>
          )}
        </SectionCard>

        {/* ── Section 2: Signal Parameters ─────────────────────────────── */}
        <SectionCard icon={SlidersHorizontal} title="Signal Parameters">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            {SIGNAL_PARAMS.map(param => (
              <div key={param.key}>
                <label style={{
                  display: 'block', fontSize: '11px', fontWeight: 700,
                  color: 'var(--text-muted)', marginBottom: '6px',
                  textTransform: 'uppercase', letterSpacing: '0.5px',
                }}>
                  {param.label}
                </label>
                <input
                  type="number"
                  value={config[param.key]}
                  min={param.min}
                  max={param.max}
                  step={param.step}
                  onChange={e => setConfig(prev => ({ ...prev, [param.key]: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    background: isDirty(param.key) ? 'rgba(240, 180, 41, 0.08)' : 'var(--bg-primary)',
                    border: isDirty(param.key) ? '1px solid #f0b429' : '1px solid var(--border)',
                    borderRadius: '6px',
                    color: 'var(--text-primary)',
                    fontSize: '14px',
                    fontWeight: 600,
                    outline: 'none',
                    fontFamily: 'monospace',
                  }}
                />
              </div>
            ))}
          </div>
        </SectionCard>

        {/* ── Section 3: Execution Mode ────────────────────────────────── */}
        <SectionCard icon={Settings} title="Execution Mode">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '15px' }}>Paper Mode</div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
                {paperMode ? 'Simulated trades only — no real money at risk' : 'Live trading enabled'}
              </div>
            </div>
            <button
              onClick={togglePaperMode}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
                color: paperMode ? '#089981' : '#f23645',
                outline: isDirty('paper_mode') ? '2px solid #f0b429' : 'none',
                outlineOffset: '4px',
                borderRadius: '4px',
              }}
            >
              {paperMode
                ? <ToggleRight size={40} />
                : <ToggleLeft size={40} />
              }
            </button>
          </div>
          {!paperMode && (
            <div style={{
              marginTop: '16px', padding: '12px 16px',
              background: 'rgba(242, 54, 69, 0.1)',
              border: '1px solid rgba(242, 54, 69, 0.3)',
              borderRadius: '6px',
              color: '#f23645',
              fontSize: '13px',
              fontWeight: 700,
              display: 'flex', alignItems: 'center', gap: '8px',
            }}>
              <AlertTriangle size={16} />
              LIVE MODE — real money will be traded.
            </div>
          )}
        </SectionCard>

        {/* Spacer */}
        <div style={{ height: '80px' }} />
      </div>

      {/* ── Section 4: Save Controls (sticky bottom bar) ───────────── */}
      <div style={{
        borderTop: '1px solid var(--border)',
        background: 'var(--bg-secondary)',
        padding: '12px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexShrink: 0,
      }}>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          {updatedAt && (
            <>
              <span style={{ fontWeight: 600 }}>Last updated:</span>{' '}
              {new Date(updatedAt).toLocaleString()}
            </>
          )}
          {hasAnyDirty && (
            <span style={{ marginLeft: '12px', color: '#f0b429', fontWeight: 600 }}>
              Unsaved changes
            </span>
          )}
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !hasAnyDirty}
          style={{
            display: 'flex', alignItems: 'center',
            padding: '10px 20px',
            background: hasAnyDirty ? '#2962ff' : 'var(--bg-tertiary)',
            color: hasAnyDirty ? '#fff' : 'var(--text-muted)',
            border: 'none',
            borderRadius: '4px',
            fontWeight: 600,
            cursor: saving || !hasAnyDirty ? 'not-allowed' : 'pointer',
            opacity: saving ? 0.7 : 1,
            fontSize: '13px',
          }}
        >
          <Save size={14} style={{ marginRight: '6px' }} />
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>

      <style>{`
        @keyframes slideDown {
          from { transform: translateY(-100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

// ── Section Card ─────────────────────────────────────────────────────────────

function SectionCard({ icon: Icon, title, children }: { icon: any; title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: '8px',
      border: '1px solid var(--border)',
      padding: '24px',
      marginBottom: '20px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px', color: '#2962ff' }}>
        <Icon size={18} style={{ marginRight: '10px' }} />
        <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>{title}</h3>
      </div>
      {children}
    </div>
  )
}
