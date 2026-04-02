import React, { useState } from 'react'
import { Shield, Save, AlertTriangle } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'

interface RiskRule {
  enabled: boolean
  value: string
}

interface RuleSet {
  maxDailyLoss: RiskRule
  maxDrawdown: RiskRule
  positionLimit: RiskRule
  cooldownPeriod: RiskRule
  stopLossRequired: RiskRule
  trailingStop: RiskRule
}

const defaultRules = (overrides?: Partial<Record<keyof RuleSet, Partial<RiskRule>>>): RuleSet => ({
  maxDailyLoss: { enabled: true, value: '2000', ...overrides?.maxDailyLoss },
  maxDrawdown: { enabled: true, value: '5', ...overrides?.maxDrawdown },
  positionLimit: { enabled: true, value: '5', ...overrides?.positionLimit },
  cooldownPeriod: { enabled: false, value: '30', ...overrides?.cooldownPeriod },
  stopLossRequired: { enabled: true, value: '2', ...overrides?.stopLossRequired },
  trailingStop: { enabled: false, value: '1.5', ...overrides?.trailingStop },
})

const RULE_LABELS: Record<keyof RuleSet, { label: string; unit: string; description: string }> = {
  maxDailyLoss: { label: 'Max Daily Loss', unit: '$', description: 'Maximum loss allowed per trading day' },
  maxDrawdown: { label: 'Max Drawdown', unit: '%', description: 'Maximum portfolio drawdown before halting' },
  positionLimit: { label: 'Position Limit', unit: 'positions', description: 'Maximum concurrent open positions' },
  cooldownPeriod: { label: 'Cooldown Period', unit: 'min', description: 'Wait time after a losing trade' },
  stopLossRequired: { label: 'Stop Loss Required', unit: '%', description: 'Mandatory stop loss on every position' },
  trailingStop: { label: 'Trailing Stop', unit: '%', description: 'Automatic trailing stop percentage' },
}

const RiskRulesView: React.FC = () => {
  const [paperRules, setPaperRules] = useState<RuleSet>(defaultRules())
  const [liveRules, setLiveRules] = useState<RuleSet>(defaultRules({
    maxDailyLoss: { value: '1000' },
    maxDrawdown: { value: '3' },
    positionLimit: { value: '3' },
    cooldownPeriod: { enabled: true, value: '60' },
    stopLossRequired: { value: '1.5' },
    trailingStop: { enabled: true, value: '1' },
  }))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await supabase.from('risk_config').upsert([
        { mode: 'paper', rules: paperRules },
        { mode: 'live', rules: liveRules },
      ])
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error('Failed to save risk config:', err)
    } finally {
      setSaving(false)
    }
  }

  const updateRule = (
    setter: React.Dispatch<React.SetStateAction<RuleSet>>,
    key: keyof RuleSet,
    field: 'enabled' | 'value',
    val: boolean | string,
  ) => {
    setter(prev => ({
      ...prev,
      [key]: { ...prev[key], [field]: val },
    }))
  }

  const renderColumn = (
    title: string,
    mode: 'PAPER' | 'LIVE',
    rules: RuleSet,
    setter: React.Dispatch<React.SetStateAction<RuleSet>>,
  ) => {
    const borderColor = mode === 'PAPER' ? '#58a6ff' : '#f85149'
    return (
      <div style={{
        flex: 1,
        backgroundColor: 'var(--bg-secondary, #161b22)',
        border: `1px solid var(--border, #30363d)`,
        borderTop: `3px solid ${borderColor}`,
        borderRadius: 8,
        padding: 24,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
          {mode === 'LIVE' && <AlertTriangle size={16} color="#f85149" />}
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: borderColor }}>
            {title}
          </h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {(Object.keys(RULE_LABELS) as (keyof RuleSet)[]).map(key => {
            const rule = rules[key]
            const meta = RULE_LABELS[key]
            return (
              <div key={key} style={{
                backgroundColor: 'var(--bg-tertiary, #21262d)',
                borderRadius: 6, padding: 14,
                opacity: rule.enabled ? 1 : 0.5,
                transition: 'opacity 0.2s',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{meta.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted, #8b949e)', marginTop: 2 }}>{meta.description}</div>
                  </div>
                  {/* Toggle */}
                  <div
                    onClick={() => updateRule(setter, key, 'enabled', !rule.enabled)}
                    style={{
                      width: 40, height: 22, borderRadius: 11,
                      backgroundColor: rule.enabled ? '#3fb950' : 'var(--border, #30363d)',
                      cursor: 'pointer', position: 'relative', transition: 'background-color 0.2s',
                      flexShrink: 0,
                    }}
                  >
                    <div style={{
                      width: 16, height: 16, borderRadius: '50%',
                      backgroundColor: '#fff',
                      position: 'absolute', top: 3,
                      left: rule.enabled ? 21 : 3,
                      transition: 'left 0.2s',
                    }} />
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input
                    type="text"
                    value={rule.value}
                    onChange={e => updateRule(setter, key, 'value', e.target.value)}
                    disabled={!rule.enabled}
                    style={{
                      flex: 1, padding: '6px 10px', borderRadius: 4,
                      border: '1px solid var(--border, #30363d)',
                      backgroundColor: 'var(--bg-primary, #0d1117)',
                      color: 'var(--text-primary, #e6edf3)',
                      fontSize: 13,
                    }}
                  />
                  <span style={{ fontSize: 12, color: 'var(--text-muted, #8b949e)', minWidth: 60 }}>
                    {meta.unit}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, backgroundColor: 'var(--bg-primary, #0d1117)', minHeight: '100%', color: 'var(--text-primary, #e6edf3)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Shield size={22} color="var(--blue, #58a6ff)" />
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Risk Rules Configuration</h2>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 18px', borderRadius: 6,
            border: 'none',
            backgroundColor: saved ? '#3fb950' : 'var(--blue, #58a6ff)',
            color: '#fff', fontWeight: 600, fontSize: 13,
            cursor: saving ? 'not-allowed' : 'pointer',
            opacity: saving ? 0.7 : 1,
            transition: 'background-color 0.2s',
          }}
        >
          <Save size={14} />
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save to Supabase'}
        </button>
      </div>

      {/* Two columns */}
      <div style={{ display: 'flex', gap: 20 }}>
        {renderColumn('PAPER Trading Rules', 'PAPER', paperRules, setPaperRules)}
        {renderColumn('LIVE Trading Rules', 'LIVE', liveRules, setLiveRules)}
      </div>
    </div>
  )
}

export default RiskRulesView
