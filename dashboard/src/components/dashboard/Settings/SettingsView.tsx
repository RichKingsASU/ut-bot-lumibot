import React from 'react'
import { Settings, Save, RefreshCw, Key, Shield, SlidersHorizontal, RotateCcw } from 'lucide-react'
import { StrategiesView } from '../Strategies/StrategiesView'
import { ContractConfigSection, CONTRACT_CONFIG_DEFAULTS } from './ContractConfigSection'
import type { ContractConfig } from './ContractConfigSection'
import { API } from '../../../lib/api'

export function SettingsView() {
  const [activeTab, setActiveTab] = React.useState<'general' | 'strategies' | 'contract'>('strategies')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Settings Header Tabs */}
      <div style={{ display: 'flex', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}>
        <button
          onClick={() => setActiveTab('strategies')}
          style={{
            padding: '16px 24px', background: activeTab === 'strategies' ? 'var(--bg-tertiary)' : 'transparent',
            border: 'none', borderBottom: activeTab === 'strategies' ? '2px solid var(--blue)' : '2px solid transparent',
            color: activeTab === 'strategies' ? 'var(--text-primary)' : 'var(--text-muted)',
            fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s'
          }}
        >
          Strategies
        </button>
        <button
          onClick={() => setActiveTab('contract')}
          style={{
            padding: '16px 24px', background: activeTab === 'contract' ? 'var(--bg-tertiary)' : 'transparent',
            border: 'none', borderBottom: activeTab === 'contract' ? '2px solid var(--blue)' : '2px solid transparent',
            color: activeTab === 'contract' ? 'var(--text-primary)' : 'var(--text-muted)',
            fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s'
          }}
        >
          Contract Config
        </button>
        <button
          onClick={() => setActiveTab('general')}
          style={{
            padding: '16px 24px', background: activeTab === 'general' ? 'var(--bg-tertiary)' : 'transparent',
            border: 'none', borderBottom: activeTab === 'general' ? '2px solid var(--blue)' : '2px solid transparent',
            color: activeTab === 'general' ? 'var(--text-primary)' : 'var(--text-muted)',
            fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s'
          }}
        >
          System Config
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {activeTab === 'strategies' && <StrategiesView />}
        {activeTab === 'contract' && <ContractConfigTab />}
        {activeTab === 'general' && <GeneralSettings />}
      </div>
    </div>
  )
}

function ContractConfigTab() {
  const [contractConfig, setContractConfig] = React.useState<ContractConfig>({ ...CONTRACT_CONFIG_DEFAULTS })
  const [savedConfig, setSavedConfig] = React.useState<ContractConfig>({ ...CONTRACT_CONFIG_DEFAULTS })
  const [saving, setSaving] = React.useState(false)
  const [toast, setToast] = React.useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [loaded, setLoaded] = React.useState(false)

  // Load config on mount
  React.useEffect(() => {
    fetch(API.optionsConfig('get'))
      .then((res) => { if (!res.ok) throw new Error(); return res.json() })
      .then((c: ContractConfig) => { setContractConfig(c); setSavedConfig(c); setLoaded(true) })
      .catch(() => setLoaded(true))
  }, [])

  // Toast auto-dismiss
  React.useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch(API.optionsConfig('save'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(contractConfig),
      })
      const result = await res.json()
      if (result.status === 'ok') {
        setSavedConfig(result.config || contractConfig)
        setToast({ type: 'success', message: 'Config saved and applied — bot will use new settings on next signal' })
      } else {
        setToast({ type: 'error', message: `Failed to save: ${result.error}` })
      }
    } catch (err: any) {
      setToast({ type: 'error', message: `Failed to save: ${err.message}` })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setContractConfig({ ...CONTRACT_CONFIG_DEFAULTS })
  }

  return (
    <div id="contract-config" style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
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
          {toast.type === 'success' ? '✓' : '✗'} {toast.message}
        </div>
      )}

      <div style={{ flex: 1, overflow: 'auto', padding: '24px', maxWidth: '900px', margin: '0 auto', width: '100%' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <SlidersHorizontal size={22} style={{ color: '#2962ff' }} />
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Contract Configuration
            </h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '4px', fontSize: '13px', margin: 0 }}>
              Configure which option contract the bot buys on each signal
            </p>
          </div>
        </div>

        <ContractConfigSection
          value={contractConfig}
          onChange={setContractConfig}
        />

        {/* Spacer for sticky bottom bar */}
        <div style={{ height: '80px' }} />
      </div>

      {/* Sticky action bar */}
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
          <span style={{ fontWeight: 600 }}>Active:</span>{' '}
          {savedConfig.expiration_mode} · {savedConfig.strike_mode} · Step {savedConfig.strike_step}
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button onClick={handleReset} style={actionSecondaryBtnStyle}>
            <RotateCcw size={14} style={{ marginRight: '6px' }} />
            Reset to Defaults
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              display: 'flex', alignItems: 'center',
              padding: '10px 20px',
              background: '#2962ff',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              fontWeight: 600,
              cursor: saving ? 'wait' : 'pointer',
              opacity: saving ? 0.7 : 1,
              fontSize: '13px',
            }}
          >
            <Save size={14} style={{ marginRight: '6px' }} />
            {saving ? 'Saving...' : 'Save & Apply'}
          </button>
        </div>
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

function GeneralSettings() {
  return (
    <div style={{ padding: '24px', maxWidth: '800px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)' }}>System Configuration</h2>
        <button style={{
          display: 'flex', alignItems: 'center', padding: '10px 20px',
          background: 'var(--blue)', color: 'white', border: 'none',
          borderRadius: '4px', fontWeight: 600, cursor: 'pointer'
        }}>
          <Save size={18} style={{ marginRight: '8px' }} />
          Save Changes
        </button>
      </div>

      <div style={{ display: 'grid', gap: '32px' }}>
        <SettingsSection icon={Shield} title="API Authentication">
          <InputGroup label="Alpaca API Key" value="PK********************" />
          <InputGroup label="Alpaca Secret Key" value="********************************" type="password" />
          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <button
              onClick={(e) => {
                const btn = e.currentTarget;
                const oldContent = btn.innerHTML;
                btn.innerHTML = 'Testing...';
                btn.disabled = true;
                setTimeout(() => {
                  btn.innerHTML = 'Connected!';
                  btn.style.borderColor = 'var(--green)';
                  btn.style.color = 'var(--green)';
                  setTimeout(() => {
                    btn.innerHTML = oldContent;
                    btn.style.borderColor = 'var(--border)';
                    btn.style.color = 'var(--text-muted)';
                    btn.disabled = false;
                  }, 2000);
                }, 1500);
              }}
              style={secondaryBtnStyle}
            >
              <RefreshCw size={14} style={{ marginRight: '6px' }} /> Test Connection
            </button>
            <button style={secondaryBtnStyle}><Key size={14} style={{ marginRight: '6px' }} /> Rotate Keys</button>
          </div>
        </SettingsSection>

        <SettingsSection icon={Settings} title="General Configuration">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0' }}>
            <div>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Dark Mode</div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Use high-contrast dark theme for low light environments</div>
            </div>
            <div style={{ width: '40px', height: '20px', background: 'var(--blue)', borderRadius: '10px', position: 'relative' }}>
              <div style={{ width: '16px', height: '16px', background: 'white', borderRadius: '50%', position: 'absolute', right: '2px', top: '2px' }} />
            </div>
          </div>
        </SettingsSection>
      </div>
    </div>
  )
}

function SettingsSection({ icon: Icon, title, children }: any) {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: '8px',
      border: '1px solid var(--border)',
      padding: '24px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px', color: 'var(--blue)' }}>
        <Icon size={20} style={{ marginRight: '10px' }} />
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>{title}</h2>
      </div>
      {children}
    </div>
  )
}

function InputGroup({ label, value, type = "text" }: any) {
  const [show, setShow] = React.useState(type !== 'password')

  return (
    <div style={{ marginBottom: '16px' }}>
      <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>{label}</label>
      <div style={{ position: 'relative' }}>
        <input
          type={show ? 'text' : 'password'}
          defaultValue={value}
          style={{
            width: '100%', padding: '10px',
            background: 'var(--bg-primary)', border: '1px solid var(--border)',
            borderRadius: '4px', color: 'var(--text-primary)', outline: 'none'
          }}
        />
        {type === 'password' && (
          <button
            onClick={() => setShow(!show)}
            style={{
              position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
              background: 'transparent', border: 'none', color: 'var(--blue)', fontSize: '10px',
              fontWeight: 700, cursor: 'pointer'
            }}
          >
            {show ? 'HIDE' : 'SHOW'}
          </button>
        )}
      </div>
    </div>
  )
}

const secondaryBtnStyle = {
  display: 'flex', alignItems: 'center', padding: '8px 12px',
  background: 'transparent', border: '1px solid var(--border)',
  borderRadius: '4px', color: 'var(--text-muted)', cursor: 'pointer',
  fontSize: '13px'
}

const actionSecondaryBtnStyle: React.CSSProperties = {
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
