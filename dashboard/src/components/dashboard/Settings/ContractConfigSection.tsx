import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Settings, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { API } from '../../../lib/api'

// ── Types ─────────────────────────────────────────────────────────────────

export interface ContractConfig {
  expiration_mode: string
  expiration_days_out: number
  strike_mode: string
  strike_step: number
  max_dte_fallback: number
}

interface PreviewData {
  status: 'ok' | 'unavailable'
  symbol?: string
  underlying_price?: number
  strike?: number
  expiration?: string
  dte?: number
  option_type?: string
  bid?: number
  ask?: number
  mid?: number
  expiration_mode_used?: string
  strike_mode_used?: string
  reason?: string
}

interface ExpirationEntry {
  date: string
  dte: number
  label: string
}

export interface ContractConfigProps {
  value: ContractConfig
  onChange: (config: ContractConfig) => void
  showPreview?: boolean
}

// ── Constants ─────────────────────────────────────────────────────────────

export const CONTRACT_CONFIG_DEFAULTS: ContractConfig = {
  expiration_mode: '0DTE',
  expiration_days_out: 0,
  strike_mode: 'ATM',
  strike_step: 1.0,
  max_dte_fallback: 7,
}

const EXPIRATION_MODES = [
  { key: '0DTE', label: '0DTE', desc: 'Same day · max gamma' },
  { key: '1DTE', label: '1DTE', desc: 'Tomorrow' },
  { key: '2DTE', label: '2DTE', desc: '2 days out' },
  { key: 'WEEKLY', label: 'WEEKLY', desc: 'Nearest Friday' },
  { key: 'BIWEEKLY', label: 'BIWEEKLY', desc: '2nd Friday out' },
  { key: 'MONTHLY', label: 'MONTHLY', desc: '3rd Friday' },
  { key: 'CUSTOM', label: 'CUSTOM', desc: 'Set days below' },
]

const STRIKE_MODES = [
  { key: 'ITM3', label: 'ITM 3', delta: 0.82, note: 'more expensive, safer' },
  { key: 'ITM2', label: 'ITM 2', delta: 0.75, note: '' },
  { key: 'ITM1', label: 'ITM 1', delta: 0.65, note: '' },
  { key: 'ATM',  label: 'ATM',   delta: 0.50, note: '' },
  { key: 'OTM1', label: 'OTM 1', delta: 0.35, note: '' },
  { key: 'OTM2', label: 'OTM 2', delta: 0.22, note: '' },
  { key: 'OTM3', label: 'OTM 3', delta: 0.12, note: 'cheaper, more leverage' },
]

// ── API helpers ───────────────────────────────────────────────────────────

async function fetchPreview(optionType: string): Promise<PreviewData> {
  const res = await fetch(`${API.optionsConfig('preview')}&option_type=${optionType}`)
  if (!res.ok) return { status: 'unavailable', reason: 'API error' }
  return res.json()
}

async function fetchExpirations(): Promise<ExpirationEntry[]> {
  try {
    const res = await fetch(API.optionsConfig('expirations'))
    if (!res.ok) return []
    const data = await res.json()
    return data.expirations || []
  } catch {
    return []
  }
}

async function fetchBotState(): Promise<{ last_signal: string; underlying_price: number | null }> {
  try {
    const res = await fetch(API.botState())
    if (!res.ok) return { last_signal: 'FLAT', underlying_price: null }
    return res.json()
  } catch {
    return { last_signal: 'FLAT', underlying_price: null }
  }
}

// ── Component ─────────────────────────────────────────────────────────────

export function ContractConfigSection({ value, onChange, showPreview = true }: ContractConfigProps) {
  const [preview, setPreview] = useState<PreviewData | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [expirations, setExpirations] = useState<ExpirationEntry[]>([])
  const [botSignal, setBotSignal] = useState<string>('FLAT')
  const [underlyingPrice, setUnderlyingPrice] = useState<number | null>(null)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const previewTimer = useRef<number | null>(null)

  // ── Load initial data ───────────────────────────────────────────────
  useEffect(() => {
    fetchExpirations().then(setExpirations)
    fetchBotState().then((s) => { setBotSignal(s.last_signal); setUnderlyingPrice(s.underlying_price) })
  }, [])

  // ── Auto-refresh preview every 30s ──────────────────────────────────
  const refreshPreview = useCallback(() => {
    if (!showPreview) return
    setPreviewLoading(true)
    const optionType = botSignal === 'SHORT' ? 'put' : 'call'
    fetchPreview(optionType)
      .then(setPreview)
      .catch(() => setPreview({ status: 'unavailable', reason: 'Failed to fetch preview' }))
      .finally(() => setPreviewLoading(false))
  }, [botSignal, showPreview])

  useEffect(() => {
    refreshPreview()
  }, [refreshPreview])

  useEffect(() => {
    if (!showPreview) return
    previewTimer.current = window.setInterval(refreshPreview, 30000)
    return () => { if (previewTimer.current) clearInterval(previewTimer.current) }
  }, [refreshPreview, showPreview])

  const marketOpen = preview?.status === 'ok'
  const basePrice = preview?.underlying_price ?? underlyingPrice ?? 580
  const step = value.strike_step

  return (
    <div>
      {/* Market status indicator */}
      {showPreview && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
          <div
            className={marketOpen ? 'pulse-dot' : ''}
            style={{
              width: 10, height: 10, borderRadius: '50%',
              background: marketOpen ? '#089981' : '#8b949e',
            }}
          />
          <span style={{ fontSize: '12px', color: marketOpen ? '#089981' : 'var(--text-muted)', fontWeight: 600 }}>
            {marketOpen ? 'Live Preview' : 'Market Closed'}
          </span>
        </div>
      )}

      {/* SECTION 1: EXPIRATION */}
      <SectionCard title="Expiration — How far out?">
        <label style={labelStyle}>Expiration Mode</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
          {EXPIRATION_MODES.map((m) => (
            <div
              key={m.key}
              onClick={() => onChange({ ...value, expiration_mode: m.key })}
              style={{
                padding: '10px 16px',
                borderRadius: '6px',
                cursor: 'pointer',
                textAlign: 'center',
                minWidth: '100px',
                border: value.expiration_mode === m.key ? '1px solid #2962ff' : '1px solid var(--border)',
                background: value.expiration_mode === m.key ? 'rgba(41,98,255,0.15)' : 'var(--bg-primary)',
                transition: 'all 0.15s',
              }}
            >
              <div style={{
                fontWeight: 700, fontSize: '13px',
                color: value.expiration_mode === m.key ? '#2962ff' : 'var(--text-primary)',
              }}>
                {m.label}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {m.desc}
              </div>
            </div>
          ))}
        </div>

        {value.expiration_mode === 'CUSTOM' && (
          <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <label style={{ ...labelStyle, marginBottom: 0 }}>Days out</label>
            <input
              type="number"
              min={0}
              max={60}
              value={value.expiration_days_out}
              onChange={(e) => onChange({ ...value, expiration_days_out: Math.max(0, Math.min(60, Number(e.target.value) || 0)) })}
              style={numberInputStyle}
            />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              0 = today, 7 = ~1 week, 30 = ~1 month
            </span>
          </div>
        )}

        <label style={labelStyle}>Available Expirations</label>
        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
          {expirations.length === 0 && (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Loading expirations...</span>
          )}
          {expirations.slice(0, 5).map((exp) => {
            const isMatch = matchesCurrentMode(value, exp)
            return (
              <div
                key={exp.date}
                style={{
                  padding: '8px 12px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  border: isMatch ? '1px solid #2962ff' : '1px solid var(--border)',
                  background: isMatch ? 'rgba(41,98,255,0.1)' : 'var(--bg-primary)',
                  color: isMatch ? '#2962ff' : 'var(--text-muted)',
                }}
              >
                <div>{exp.date}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
                  <span>{exp.dte} DTE</span>
                  {exp.label.includes('Weekly') && (
                    <span style={{
                      background: 'rgba(41,98,255,0.2)',
                      color: '#2962ff',
                      padding: '0 4px',
                      borderRadius: '2px',
                      fontSize: '9px',
                    }}>W</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </SectionCard>

      {/* SECTION 2: STRIKE */}
      <SectionCard title="Strike — How far from price?">
        <label style={labelStyle}>Strike Selection</label>
        <div style={{ borderRadius: '6px', overflow: 'hidden', border: '1px solid var(--border)', marginBottom: '16px' }}>
          {STRIKE_MODES.map((s) => {
            const isSelected = value.strike_mode === s.key
            const idx = STRIKE_MODES.findIndex((x) => x.key === s.key)
            const atmIdx = STRIKE_MODES.findIndex((x) => x.key === 'ATM')
            const offset = (idx - atmIdx) * step
            const strikeVal = Math.round(basePrice) + offset

            return (
              <div
                key={s.key}
                onClick={() => onChange({ ...value, strike_mode: s.key })}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '90px 80px 80px 1fr',
                  alignItems: 'center',
                  padding: '10px 16px',
                  cursor: 'pointer',
                  borderBottom: '1px solid var(--border)',
                  background: isSelected ? 'rgba(41,98,255,0.12)' : 'transparent',
                  transition: 'background 0.1s',
                }}
              >
                <div style={{ fontWeight: 700, fontSize: '13px', color: isSelected ? '#2962ff' : 'var(--text-primary)' }}>
                  {isSelected ? '▶ ' : '  '}{s.label}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                  {strikeVal.toFixed(0)}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  δ ~{s.delta.toFixed(2)}
                </div>
                {s.note && (
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'right' }}>
                    {s.note}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ ...labelStyle, marginBottom: 0 }}>Strike Step</label>
          <input
            type="number"
            min={0.5}
            max={10}
            step={0.5}
            value={value.strike_step}
            onChange={(e) => onChange({ ...value, strike_step: Math.max(0.5, Math.min(10, Number(e.target.value) || 1)) })}
            style={numberInputStyle}
          />
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Dollar width between strikes. SPY=1.0, QQQ=1.0, IWM=1.0
          </span>
        </div>
      </SectionCard>

      {/* SECTION 3: LIVE CONTRACT PREVIEW */}
      {showPreview && (
        <SectionCard title="Live Contract Preview">
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
            <button
              onClick={refreshPreview}
              disabled={previewLoading}
              style={{
                ...secondaryBtnStyle,
                opacity: previewLoading ? 0.5 : 1,
              }}
            >
              <RefreshCw size={14} style={{ marginRight: '6px', animation: previewLoading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>

          {previewLoading && !preview && (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              Loading preview...
            </div>
          )}

          {preview?.status === 'ok' && (
            <PreviewCard preview={preview} botSignal={botSignal} />
          )}

          {preview?.status === 'unavailable' && (
            <div style={{
              padding: '32px',
              borderRadius: '6px',
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              textAlign: 'center',
              color: 'var(--text-muted)',
            }}>
              <div style={{ fontSize: '14px', marginBottom: '8px' }}>
                Market is closed or no contracts available for current settings.
              </div>
              <div style={{ fontSize: '12px' }}>
                {preview.reason || 'Preview will refresh automatically when market opens.'}
              </div>
            </div>
          )}
        </SectionCard>
      )}

      {/* SECTION 4: ADVANCED / FALLBACK */}
      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: '8px',
        border: '1px solid var(--border)',
      }}>
        <div
          onClick={() => setAdvancedOpen(!advancedOpen)}
          style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '16px 20px',
            cursor: 'pointer',
            color: 'var(--text-muted)',
          }}
        >
          <span style={{ fontWeight: 600, fontSize: '14px' }}>
            {advancedOpen ? '▼' : '▶'} Advanced
          </span>
          {advancedOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
        {advancedOpen && (
          <div style={{ padding: '0 20px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ ...labelStyle, marginBottom: 0 }}>Max DTE Fallback</label>
              <input
                type="number"
                min={0}
                max={60}
                value={value.max_dte_fallback}
                onChange={(e) => onChange({ ...value, max_dte_fallback: Math.max(0, Math.min(60, Number(e.target.value) || 0)) })}
                style={numberInputStyle}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>days</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px' }}>
              If no contracts exist on target date, search this many additional days forward before giving up
            </p>
          </div>
        )}
      </div>

      {/* Inline keyframes */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: '8px',
      border: '1px solid var(--border)',
      padding: '20px',
      marginBottom: '24px',
    }}>
      <h2 style={{
        fontSize: '16px', fontWeight: 700,
        color: 'var(--text-primary)',
        marginBottom: '16px',
        display: 'flex', alignItems: 'center', gap: '8px',
      }}>
        <Settings size={18} style={{ color: '#2962ff' }} />
        {title}
      </h2>
      {children}
    </div>
  )
}

function PreviewCard({ preview, botSignal }: { preview: PreviewData; botSignal: string }) {
  const bid = preview.bid ?? 0
  const ask = preview.ask ?? 0
  const mid = preview.mid ?? 0
  const spread = ask - bid
  const spreadPct = mid > 0 ? (spread / mid) * 100 : 0
  const costPerContract = mid * 100

  const barWidth = Math.min(spreadPct / 10 * 100, 100)
  let spreadQuality: { label: string; color: string }
  if (spreadPct < 3) {
    spreadQuality = { label: 'GOOD', color: '#089981' }
  } else if (spreadPct <= 7) {
    spreadQuality = { label: 'FAIR', color: '#e3b341' }
  } else {
    spreadQuality = { label: 'WIDE', color: '#f23645' }
  }

  const optType = (preview.option_type || 'call').toUpperCase()
  const expLabel = preview.expiration
    ? new Date(preview.expiration + 'T12:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : ''

  return (
    <div style={{
      borderRadius: '6px',
      background: 'var(--bg-primary)',
      border: '1px solid var(--border)',
      padding: '20px',
    }}>
      <div style={{
        fontSize: '15px', fontWeight: 700,
        color: optType === 'CALL' ? '#089981' : '#f23645',
        marginBottom: '16px',
      }}>
        {optType} · SPY · Strike {preview.strike?.toFixed(1)} · Exp {expLabel} ({preview.dte} DTE)
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '16px', marginBottom: '16px' }}>
        <DetailCell label="Contract" value={preview.symbol || ''} mono />
        <DetailCell label="Underlying" value={`$${preview.underlying_price?.toFixed(2)}`} />
        <DetailCell label="Bid" value={`$${bid.toFixed(2)}`} />
        <DetailCell label="Ask" value={`$${ask.toFixed(2)}`} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '16px', marginBottom: '20px' }}>
        <DetailCell label="Mid" value={`$${mid.toFixed(3)}`} />
        <DetailCell label="Spread" value={`$${spread.toFixed(2)} (${spreadPct.toFixed(1)}%)`} />
        <DetailCell label="Est. Cost (1 ct)" value={`$${costPerContract.toFixed(2)}`} />
        <DetailCell label="Mode" value={`${preview.expiration_mode_used} / ${preview.strike_mode_used}`} />
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
            Spread Quality
          </span>
          <span style={{ fontSize: '12px', fontWeight: 700, color: spreadQuality.color }}>
            {spreadQuality.label}
          </span>
        </div>
        <div style={{ height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${barWidth}%`,
            background: spreadQuality.color,
            borderRadius: '3px',
            transition: 'width 0.3s ease',
          }} />
        </div>
        {spreadQuality.label === 'WIDE' && (
          <div style={{ fontSize: '11px', color: '#f23645', marginTop: '6px', fontWeight: 500 }}>
            {'\u26A0'} Wide spread detected {'\u2014'} slippage may be significant
          </div>
        )}
      </div>
    </div>
  )
}

function DetailCell({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '4px' }}>
        {label}
      </div>
      <div style={{
        fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500,
        fontFamily: mono ? 'monospace' : 'inherit',
        wordBreak: 'break-all',
      }}>
        {value}
      </div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────

function matchesCurrentMode(config: ContractConfig, exp: ExpirationEntry): boolean {
  if (config.expiration_mode === '0DTE') return exp.dte === 0
  if (config.expiration_mode === '1DTE') return exp.dte === 1
  if (config.expiration_mode === '2DTE') return exp.dte === 2
  return false
}

// ── Shared styles ─────────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '11px',
  fontWeight: 700,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: '8px',
}

const numberInputStyle: React.CSSProperties = {
  width: '80px',
  padding: '8px 10px',
  background: 'var(--bg-primary)',
  border: '1px solid var(--border)',
  borderRadius: '4px',
  color: 'var(--text-primary)',
  fontSize: '13px',
  outline: 'none',
  textAlign: 'center',
}

const secondaryBtnStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  padding: '8px 14px',
  background: 'transparent',
  border: '1px solid var(--border)',
  borderRadius: '4px',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontSize: '13px',
  fontWeight: 500,
}
