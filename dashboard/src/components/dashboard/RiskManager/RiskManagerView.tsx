import React, { useEffect, useMemo, useState } from 'react'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'

const MAX_DAILY_LOSS_CAP = 1_000_000

type FieldErrors = {
  maxDailyLoss?: string
  maxPositionPct?: string
}

type Toast = { kind: 'success' | 'error'; message: string } | null

const validateMaxDailyLoss = (raw: string, equityCap?: number): string | undefined => {
  if (raw === '' || raw == null) return 'Daily loss limit must be a positive dollar amount'
  const n = Number(raw)
  if (!Number.isFinite(n) || n <= 0) {
    return 'Daily loss limit must be a positive dollar amount'
  }
  const cap = equityCap && equityCap > 0 ? equityCap : MAX_DAILY_LOSS_CAP
  if (n > cap) {
    return 'Daily loss limit must be a positive dollar amount'
  }
  return undefined
}

const validateMaxPositionPct = (raw: string): string | undefined => {
  if (raw === '' || raw == null) return 'Position size must be between 1% and 100%'
  const n = Number(raw)
  if (!Number.isFinite(n) || n < 1 || n > 100) {
    return 'Position size must be between 1% and 100%'
  }
  return undefined
}

const RiskManagerView: React.FC = () => {
  const [tradingEnabled, setTradingEnabled] = useState(true)
  const [maxDailyLoss, setMaxDailyLoss] = useState<string>('')
  const [maxPositionPct, setMaxPositionPct] = useState<string>('')
  const [accountEquity, setAccountEquity] = useState<number | undefined>(undefined)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [touched, setTouched] = useState<{ maxDailyLoss?: boolean; maxPositionPct?: boolean }>({})
  const [toast, setToast] = useState<Toast>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await supabase
          .from('user_settings')
          .select('trading_enabled, max_daily_loss, max_position_pct, account_equity')
          .eq('id', 1)
          .single()
        if (data) {
          setTradingEnabled(data.trading_enabled ?? true)
          setMaxDailyLoss(data.max_daily_loss != null ? String(data.max_daily_loss) : '')
          setMaxPositionPct(data.max_position_pct != null ? String(data.max_position_pct) : '')
          if (typeof data.account_equity === 'number' && data.account_equity > 0) {
            setAccountEquity(data.account_equity)
          }
        }
      } catch {
        // Row may not exist yet — keep defaults
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

  const liveErrors = useMemo<FieldErrors>(() => ({
    maxDailyLoss: validateMaxDailyLoss(maxDailyLoss, accountEquity),
    maxPositionPct: validateMaxPositionPct(maxPositionPct),
  }), [maxDailyLoss, maxPositionPct, accountEquity])

  const hasAnyError = Boolean(liveErrors.maxDailyLoss || liveErrors.maxPositionPct)

  const showError = (field: keyof FieldErrors): string | undefined => {
    if (errors[field]) return errors[field]
    if (touched[field]) return liveErrors[field]
    return undefined
  }

  const toggleKillSwitch = async () => {
    const newVal = !tradingEnabled
    setTradingEnabled(newVal)
    try {
      await supabase
        .from('user_settings')
        .upsert({ id: 1, trading_enabled: newVal }, { onConflict: 'id' })
    } catch {
      console.error('Failed to update trading_enabled')
    }
  }

  const saveSettings = async () => {
    const submitErrors: FieldErrors = {
      maxDailyLoss: validateMaxDailyLoss(maxDailyLoss, accountEquity),
      maxPositionPct: validateMaxPositionPct(maxPositionPct),
    }
    setErrors(submitErrors)
    setTouched({ maxDailyLoss: true, maxPositionPct: true })
    if (submitErrors.maxDailyLoss || submitErrors.maxPositionPct) {
      return
    }

    setSaving(true)
    try {
      const { error: dbError } = await supabase
        .from('user_settings')
        .upsert(
          {
            id: 1,
            max_daily_loss: parseFloat(maxDailyLoss),
            max_position_pct: parseFloat(maxPositionPct),
          },
          { onConflict: 'id' }
        )
      if (dbError) throw dbError
      setToast({ kind: 'success', message: 'Risk settings saved' })
    } catch {
      setToast({ kind: 'error', message: 'Failed to save — please try again' })
    } finally {
      setSaving(false)
    }
  }

  const pageStyle: React.CSSProperties = {
    padding: 24,
    backgroundColor: 'var(--bg-primary, #0d1117)',
    minHeight: '100%',
    color: 'var(--text-primary, #e6edf3)',
  }

  const cardBase: React.CSSProperties = {
    border: '1px solid var(--border, #30363d)',
    borderRadius: 8,
    padding: 20,
    marginBottom: 16,
    backgroundColor: 'var(--bg-secondary, #161b22)',
  }

  const inputStyle: React.CSSProperties = {
    width: 180,
    padding: '8px 12px',
    borderRadius: 6,
    border: '1px solid var(--border, #30363d)',
    backgroundColor: 'var(--bg-tertiary, #21262d)',
    color: 'var(--text-primary, #e6edf3)',
    fontSize: 14,
    boxSizing: 'border-box',
  }

  const errorInputStyle: React.CSSProperties = {
    ...inputStyle,
    borderColor: '#f85149',
  }

  const errorTextStyle: React.CSSProperties = {
    color: '#f85149',
    fontSize: 12,
    marginTop: 6,
  }

  const killCardStyle: React.CSSProperties = {
    ...cardBase,
    borderColor: tradingEnabled ? 'rgba(63,185,80,0.4)' : 'rgba(248,81,73,0.4)',
    backgroundColor: tradingEnabled ? 'rgba(63,185,80,0.08)' : 'rgba(248,81,73,0.12)',
  }

  const toastStyle: React.CSSProperties | null = toast
    ? {
        position: 'fixed',
        top: 24,
        right: 24,
        zIndex: 1000,
        padding: '10px 16px',
        borderRadius: 6,
        fontSize: 13,
        fontWeight: 500,
        color: '#fff',
        backgroundColor: toast.kind === 'success' ? '#238636' : '#da3633',
        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
      }
    : null

  const dailyLossError = showError('maxDailyLoss')
  const positionPctError = showError('maxPositionPct')
  const saveDisabled = saving || hasAnyError

  return (
    <div style={pageStyle}>
      <PageHeader title="Risk manager" subtitle="Kill switch & limits" />

      {toastStyle && toast && (
        <div role="status" aria-live="polite" style={toastStyle}>
          {toast.message}
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--text-muted, #8b949e)', fontSize: 13 }}>Loading...</div>
      ) : (
        <div style={{ maxWidth: 640 }}>
          {/* Kill Switch */}
          <div style={killCardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
                  {tradingEnabled ? 'Trading Enabled' : 'Trading STOPPED'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)' }}>
                  {tradingEnabled
                    ? 'Bot will execute trades when signals fire'
                    : 'Bot will skip all trades — kill switch is active'}
                </div>
              </div>
              <button
                onClick={toggleKillSwitch}
                style={{
                  padding: '10px 18px',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: 'none',
                  color: '#fff',
                  backgroundColor: tradingEnabled ? '#da3633' : '#238636',
                  whiteSpace: 'nowrap',
                }}
              >
                {tradingEnabled ? 'Stop Trading' : 'Resume Trading'}
              </button>
            </div>
          </div>

          {/* Daily Loss Limit */}
          <div style={cardBase}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Max daily loss ($)</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)', marginBottom: 12 }}>
              Bot stops trading if this loss is reached today
            </div>
            <input
              type="number"
              min="0.01"
              max={accountEquity && accountEquity > 0 ? accountEquity : MAX_DAILY_LOSS_CAP}
              step="0.01"
              value={maxDailyLoss}
              onChange={e => {
                setMaxDailyLoss(e.target.value)
                if (errors.maxDailyLoss) {
                  setErrors(prev => ({ ...prev, maxDailyLoss: undefined }))
                }
              }}
              onBlur={() => {
                setTouched(prev => ({ ...prev, maxDailyLoss: true }))
                setErrors(prev => ({
                  ...prev,
                  maxDailyLoss: validateMaxDailyLoss(maxDailyLoss, accountEquity),
                }))
              }}
              placeholder="e.g. 500"
              aria-invalid={Boolean(dailyLossError)}
              aria-describedby={dailyLossError ? 'maxDailyLoss-error' : undefined}
              style={dailyLossError ? errorInputStyle : inputStyle}
            />
            {dailyLossError && (
              <div id="maxDailyLoss-error" style={errorTextStyle}>
                {dailyLossError}
              </div>
            )}
          </div>

          {/* Max Position Size */}
          <div style={cardBase}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
              Max position size (% of portfolio)
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)', marginBottom: 12 }}>
              Maximum allocation per single trade
            </div>
            <input
              type="number"
              min="1"
              max="100"
              step="1"
              value={maxPositionPct}
              onChange={e => {
                setMaxPositionPct(e.target.value)
                if (errors.maxPositionPct) {
                  setErrors(prev => ({ ...prev, maxPositionPct: undefined }))
                }
              }}
              onBlur={() => {
                setTouched(prev => ({ ...prev, maxPositionPct: true }))
                setErrors(prev => ({
                  ...prev,
                  maxPositionPct: validateMaxPositionPct(maxPositionPct),
                }))
              }}
              placeholder="e.g. 10"
              aria-invalid={Boolean(positionPctError)}
              aria-describedby={positionPctError ? 'maxPositionPct-error' : undefined}
              style={positionPctError ? errorInputStyle : inputStyle}
            />
            {positionPctError && (
              <div id="maxPositionPct-error" style={errorTextStyle}>
                {positionPctError}
              </div>
            )}
          </div>

          <button
            onClick={saveSettings}
            disabled={saveDisabled}
            style={{
              padding: '9px 18px',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              cursor: saveDisabled ? 'not-allowed' : 'pointer',
              border: '1px solid var(--border, #30363d)',
              backgroundColor: 'var(--bg-tertiary, #21262d)',
              color: 'var(--text-primary, #e6edf3)',
              opacity: saveDisabled ? 0.6 : 1,
            }}
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      )}
    </div>
  )
}

export default RiskManagerView
