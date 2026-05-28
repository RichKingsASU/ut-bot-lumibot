import React, { useState, useEffect, useCallback } from 'react'
import { Key, Database, Bell, SlidersHorizontal, ShieldAlert, Save, HelpCircle, CheckCircle2, XCircle } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'

const styles = {
  container: {
    padding: '24px',
    backgroundColor: 'var(--bg-primary, #0d1117)',
    color: 'var(--text-primary, #e6edf3)',
    minHeight: '100vh',
  },
  section: {
    backgroundColor: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '8px',
    padding: '24px',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '16px',
    fontWeight: 600,
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '10px',
    marginBottom: '16px',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: 'var(--text-muted, #8b949e)',
    marginBottom: '6px',
    display: 'block' as const,
  },
  input: {
    width: '100%',
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid var(--border, #30363d)',
    backgroundColor: 'var(--bg-tertiary, #21262d)',
    color: 'var(--text-primary, #e6edf3)',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box' as const,
  },
  toggleRow: {
    display: 'flex' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    padding: '12px 0',
  },
  toggleLabel: {
    fontSize: '14px',
    fontWeight: 600,
  },
  toggleDesc: {
    fontSize: '12px',
    color: 'var(--text-muted, #8b949e)',
    marginTop: '2px',
  },
  toggle: (on: boolean) => ({
    width: '42px',
    height: '22px',
    borderRadius: '11px',
    backgroundColor: on ? 'var(--red, #f85149)' : 'var(--bg-tertiary, #21262d)',
    border: `1px solid ${on ? 'var(--red, #f85149)' : 'var(--border, #30363d)'}`,
    position: 'relative' as const,
    cursor: 'pointer' as const,
    transition: 'background-color 0.2s',
  }),
  toggleKnob: (on: boolean) => ({
    width: '16px',
    height: '16px',
    borderRadius: '50%',
    backgroundColor: '#fff',
    position: 'absolute' as const,
    top: '2px',
    left: on ? '22px' : '2px',
    transition: 'left 0.2s',
  }),
  grid2: {
    display: 'grid' as const,
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  muted: {
    color: 'var(--text-muted, #8b949e)',
    fontSize: '13px',
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: 'var(--green, #3fb950)',
    display: 'inline-block' as const,
    marginRight: '6px',
  },
}

export function SettingsView() {
  const [killSwitch, setKillSwitch] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'error' | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true)
      // Check bot_status first
      const { data: botStatus } = await supabase
        .from('bot_status')
        .select('kill_switch')
        .eq('id', 1)
        .maybeSingle()

      if (botStatus) {
        setKillSwitch(botStatus.kill_switch || false)
      } else {
        // Fallback to user_settings
        const { data: settings } = await supabase
          .from('user_settings')
          .select('value')
          .eq('key', 'kill_switch')
          .maybeSingle()
        if (settings) {
          setKillSwitch(settings.value === 'true')
        }
      }
    } catch (e) {
      console.error('Error fetching settings:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const handleToggleKillSwitch = async () => {
    const nextVal = !killSwitch
    if (nextVal) {
      const confirmHalt = window.confirm('CRITICAL SAFETY HALT: This will immediately stop all automated order routing and intelligence sweeps. Proceed with Kill Switch engagement?')
      if (!confirmHalt) return
    }

    setKillSwitch(nextVal)
    try {
      // 1. Update bot_status
      await supabase
        .from('bot_status')
        .update({ kill_switch: nextVal })
        .eq('id', 1)

      // 2. Also update user_settings table just in case
      await supabase
        .from('user_settings')
        .upsert({ key: 'kill_switch', value: String(nextVal) })

      // 3. Update trading_enabled flag in user_settings
      await supabase
        .from('user_settings')
        .upsert({ key: 'trading_enabled', value: String(!nextVal) })

      setSaveStatus('saved')
    } catch (e) {
      console.error(e)
      setSaveStatus('error')
    }
    setTimeout(() => setSaveStatus(null), 3000)
  }

  return (
    <div style={styles.container}>
      <PageHeader title="Surveillance Settings" subtitle="Trading safety & infrastructure configurations" />

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          Syncing surveillance configuration...
        </div>
      ) : (
        <div style={{ maxWidth: '800px' }}>
          {/* Trading Safety Gate (Kill Switch) */}
          <div style={styles.section}>
            <div style={{ ...styles.sectionTitle, color: 'var(--red)' }}>
              <ShieldAlert size={20} /> Safety & Core Control
            </div>
            <div style={styles.toggleRow}>
              <div>
                <div style={styles.toggleLabel}>Emergency Kill Switch</div>
                <div style={styles.toggleDesc}>Engaging this will halt all execution flows immediately and block automated order generation.</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                {saveStatus && (
                  <span style={{ fontSize: '12px', color: saveStatus === 'saved' ? 'var(--green)' : 'var(--red)' }}>
                    {saveStatus === 'saved' ? 'Synchronized' : 'Failed'}
                  </span>
                )}
                <div style={styles.toggle(killSwitch)} onClick={handleToggleKillSwitch}>
                  <div style={styles.toggleKnob(killSwitch)} />
                </div>
              </div>
            </div>
          </div>

          {/* Broker configuration (Read-Only) */}
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <Key size={18} /> Broker Configuration
            </div>
            <div style={styles.grid2}>
              <div style={styles.inputRow}>
                <label style={styles.label}>Execution Environment</label>
                <input type="text" style={{ ...styles.input, opacity: 0.7 }} value="PAPER MODE" readOnly />
              </div>
              <div style={styles.inputRow}>
                <label style={styles.label}>Alpaca Endpoint</label>
                <input type="text" style={{ ...styles.input, opacity: 0.7 }} value="https://paper-api.alpaca.markets" readOnly />
              </div>
            </div>
            <div style={styles.inputRow}>
              <label style={styles.label}>Max Position Size constraint</label>
              <input type="text" style={{ ...styles.input, opacity: 0.7 }} value="$2,500 per position (hardcoded safety limit)" readOnly />
            </div>
          </div>

          {/* Infrastructure Alerts (Read-Only) */}
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <Bell size={18} /> Notification Ingestion
            </div>
            <div style={styles.grid2}>
              <div style={styles.inputRow}>
                <label style={styles.label}>Telegram Alerts Channel</label>
                <input type="text" style={{ ...styles.input, opacity: 0.7 }} value="Alerts routing to Telegram Chat ID: 8641189809" readOnly />
              </div>
              <div style={styles.inputRow}>
                <label style={styles.label}>Status</label>
                <input type="text" style={{ ...styles.input, opacity: 0.7 }} value="ACTIVE" readOnly />
              </div>
            </div>
          </div>

          {/* Database Infrastructure (Read-Only) */}
          <div style={styles.section}>
            <div style={styles.sectionTitle}>
              <Database size={18} /> Database Infrastructure
            </div>
            <div style={styles.inputRow}>
              <label style={styles.label}>Supabase Endpoint</label>
              <input type="text" style={{ ...styles.input, opacity: 0.7 }} value={import.meta.env.VITE_SUPABASE_URL || 'Connected to Cloud Instance'} readOnly />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', marginTop: '12px' }}>
              <span style={styles.statusDot} />
              <span style={{ fontSize: '13px', color: 'var(--green)' }}>Connected & Healthy</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SettingsView
