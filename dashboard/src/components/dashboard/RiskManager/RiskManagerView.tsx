import React, { useEffect, useState } from 'react'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'

const RiskManagerView: React.FC = () => {
  const [tradingEnabled, setTradingEnabled] = useState(true)
  const [maxDailyLoss, setMaxDailyLoss] = useState<string>('')
  const [maxPositionPct, setMaxPositionPct] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await supabase
          .from('user_settings')
          .select('trading_enabled, max_daily_loss, max_position_pct')
          .eq('id', 1)
          .single()
        if (data) {
          setTradingEnabled(data.trading_enabled ?? true)
          setMaxDailyLoss(data.max_daily_loss != null ? String(data.max_daily_loss) : '')
          setMaxPositionPct(data.max_position_pct != null ? String(data.max_position_pct) : '')
        }
      } catch {
        // Row may not exist yet — keep defaults
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

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
    setSaving(true)
    try {
      await supabase
        .from('user_settings')
        .upsert(
          {
            id: 1,
            max_daily_loss: maxDailyLoss === '' ? null : parseFloat(maxDailyLoss),
            max_position_pct: maxPositionPct === '' ? null : parseFloat(maxPositionPct),
          },
          { onConflict: 'id' }
        )
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      console.error('Failed to save risk settings')
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

  const killCardStyle: React.CSSProperties = {
    ...cardBase,
    borderColor: tradingEnabled ? 'rgba(63,185,80,0.4)' : 'rgba(248,81,73,0.4)',
    backgroundColor: tradingEnabled ? 'rgba(63,185,80,0.08)' : 'rgba(248,81,73,0.12)',
  }

  return (
    <div style={pageStyle}>
      <PageHeader title="Risk manager" subtitle="Kill switch & limits" />

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
              value={maxDailyLoss}
              onChange={e => setMaxDailyLoss(e.target.value)}
              placeholder="e.g. 500"
              style={inputStyle}
            />
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
              value={maxPositionPct}
              onChange={e => setMaxPositionPct(e.target.value)}
              placeholder="e.g. 10"
              style={inputStyle}
            />
          </div>

          <button
            onClick={saveSettings}
            disabled={saving}
            style={{
              padding: '9px 18px',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              cursor: saving ? 'default' : 'pointer',
              border: '1px solid var(--border, #30363d)',
              backgroundColor: saved ? '#238636' : 'var(--bg-tertiary, #21262d)',
              color: 'var(--text-primary, #e6edf3)',
            }}
          >
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Settings'}
          </button>
        </div>
      )}
    </div>
  )
}

export default RiskManagerView
