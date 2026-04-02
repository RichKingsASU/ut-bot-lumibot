import React, { useState } from 'react'
import { Settings as SettingsIcon, Key, Database, Bell, SlidersHorizontal, ChevronDown, ChevronUp, Save, Eye, EyeOff } from 'lucide-react'

const styles = {
  container: {
    padding: '24px',
    backgroundColor: 'var(--bg-primary, #0d1117)',
    color: 'var(--text-primary, #e6edf3)',
    minHeight: '100vh',
  },
  header: {
    fontSize: '24px',
    fontWeight: 700,
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '10px',
    marginBottom: '24px',
  },
  accordion: {
    backgroundColor: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '8px',
    marginBottom: '12px',
    overflow: 'hidden' as const,
  },
  accordionHeader: {
    display: 'flex' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    padding: '16px 20px',
    cursor: 'pointer' as const,
    userSelect: 'none' as const,
  },
  accordionTitle: {
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '10px',
    fontSize: '15px',
    fontWeight: 600,
  },
  accordionBody: (open: boolean) => ({
    maxHeight: open ? '600px' : '0',
    overflow: 'hidden' as const,
    transition: 'max-height 0.3s ease',
  }),
  accordionContent: {
    padding: '0 20px 20px',
    borderTop: '1px solid var(--border, #30363d)',
    paddingTop: '16px',
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
  inputRow: {
    marginBottom: '14px',
  },
  inputWithIcon: {
    position: 'relative' as const,
  },
  eyeBtn: {
    position: 'absolute' as const,
    right: '10px',
    top: '50%',
    transform: 'translateY(-50%)',
    background: 'none',
    border: 'none',
    color: 'var(--text-muted, #8b949e)',
    cursor: 'pointer' as const,
    padding: '2px',
  },
  btn: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: '1px solid var(--border, #30363d)',
    backgroundColor: 'var(--bg-tertiary, #21262d)',
    color: 'var(--text-primary, #e6edf3)',
    cursor: 'pointer' as const,
    fontSize: '13px',
    display: 'inline-flex' as const,
    alignItems: 'center' as const,
    gap: '6px',
  },
  btnPrimary: {
    padding: '8px 20px',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: 'var(--blue, #58a6ff)',
    color: '#0d1117',
    cursor: 'pointer' as const,
    fontSize: '13px',
    fontWeight: 600,
    display: 'inline-flex' as const,
    alignItems: 'center' as const,
    gap: '6px',
  },
  statusDot: (connected: boolean) => ({
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: connected ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
    display: 'inline-block' as const,
    marginRight: '6px',
  }),
  toggleRow: {
    display: 'flex' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    padding: '10px 0',
  },
  toggleLabel: {
    fontSize: '14px',
    fontWeight: 500,
  },
  toggle: (on: boolean) => ({
    width: '42px',
    height: '22px',
    borderRadius: '11px',
    backgroundColor: on ? 'var(--green, #3fb950)' : 'var(--bg-tertiary, #21262d)',
    border: `1px solid ${on ? 'var(--green, #3fb950)' : 'var(--border, #30363d)'}`,
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
  select: {
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
  grid2: {
    display: 'grid' as const,
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  muted: {
    color: 'var(--text-muted, #8b949e)',
    fontSize: '13px',
  },
}

type Section = 'broker' | 'database' | 'notifications' | 'strategy'

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <div style={styles.toggle(on)} onClick={onClick}>
      <div style={styles.toggleKnob(on)} />
    </div>
  )
}

function MaskedInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [visible, setVisible] = useState(false)
  return (
    <div style={styles.inputRow}>
      <label style={styles.label}>{label}</label>
      <div style={styles.inputWithIcon}>
        <input
          type={visible ? 'text' : 'password'}
          style={styles.input}
          placeholder={placeholder || ''}
          value={value}
          onChange={e => onChange(e.target.value)}
        />
        <button style={styles.eyeBtn} onClick={() => setVisible(!visible)}>
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  )
}

export function SettingsView() {
  const [openSections, setOpenSections] = useState<Set<Section>>(new Set(['broker']))
  const [alpacaKey, setAlpacaKey] = useState('')
  const [alpacaSecret, setAlpacaSecret] = useState('')
  const [paperMode, setPaperMode] = useState(true)
  const [supabaseUrl] = useState('https://your-project.supabase.co')
  const [supabaseKey, setSupabaseKey] = useState('')
  const [dbConnected] = useState(true)
  const [telegramToken, setTelegramToken] = useState('')
  const [telegramChatId, setTelegramChatId] = useState('')
  const [emailNotifs, setEmailNotifs] = useState(false)
  const [pushNotifs, setPushNotifs] = useState(true)
  const [quietStart, setQuietStart] = useState('22:00')
  const [quietEnd, setQuietEnd] = useState('07:00')
  const [defaultSymbol, setDefaultSymbol] = useState('IWM')
  const [defaultTimeframe, setDefaultTimeframe] = useState('1m')
  const [atrPeriod, setAtrPeriod] = useState('10')
  const [sensitivity, setSensitivity] = useState('1.0')
  const [autoStart, setAutoStart] = useState(false)

  const toggleSection = (section: Section) => {
    setOpenSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) next.delete(section)
      else next.add(section)
      return next
    })
  }

  const isOpen = (section: Section) => openSections.has(section)

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <SettingsIcon size={22} />
        Settings
      </div>

      {/* BROKER */}
      <div style={styles.accordion}>
        <div style={styles.accordionHeader} onClick={() => toggleSection('broker')}>
          <div style={styles.accordionTitle}>
            <Key size={18} /> Broker Configuration
          </div>
          {isOpen('broker') ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        <div style={styles.accordionBody(isOpen('broker'))}>
          <div style={styles.accordionContent}>
            <div style={styles.grid2}>
              <MaskedInput label="Alpaca API Key" value={alpacaKey} onChange={setAlpacaKey} placeholder="AKXXXXXXXXXXXXXXXXXX" />
              <MaskedInput label="Alpaca Secret Key" value={alpacaSecret} onChange={setAlpacaSecret} placeholder="Enter secret key" />
            </div>
            <div style={styles.inputRow}>
              <label style={styles.label}>Base URL</label>
              <input
                type="text"
                style={{ ...styles.input, opacity: 0.7 }}
                value={paperMode ? 'https://paper-api.alpaca.markets' : 'https://api.alpaca.markets'}
                readOnly
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '8px' }}>
              <button style={styles.btn}>Test Connection</button>
              <div style={styles.toggleRow}>
                <span style={{ ...styles.toggleLabel, marginRight: '10px' }}>{paperMode ? 'Paper Mode' : 'Live Mode'}</span>
                <Toggle on={!paperMode} onClick={() => setPaperMode(!paperMode)} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* DATABASE */}
      <div style={styles.accordion}>
        <div style={styles.accordionHeader} onClick={() => toggleSection('database')}>
          <div style={styles.accordionTitle}>
            <Database size={18} /> Database Configuration
          </div>
          {isOpen('database') ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        <div style={styles.accordionBody(isOpen('database'))}>
          <div style={styles.accordionContent}>
            <div style={styles.inputRow}>
              <label style={styles.label}>Supabase URL</label>
              <input type="text" style={{ ...styles.input, opacity: 0.7 }} value={supabaseUrl} readOnly />
            </div>
            <MaskedInput label="Supabase Anon Key" value={supabaseKey} onChange={setSupabaseKey} placeholder="Enter anon key" />
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '8px' }}>
              <button style={styles.btn}>Test Connection</button>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span style={styles.statusDot(dbConnected)} />
                <span style={{ fontSize: '13px', color: dbConnected ? 'var(--green, #3fb950)' : 'var(--red, #f85149)' }}>
                  {dbConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* NOTIFICATIONS */}
      <div style={styles.accordion}>
        <div style={styles.accordionHeader} onClick={() => toggleSection('notifications')}>
          <div style={styles.accordionTitle}>
            <Bell size={18} /> Notifications
          </div>
          {isOpen('notifications') ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        <div style={styles.accordionBody(isOpen('notifications'))}>
          <div style={styles.accordionContent}>
            <div style={styles.grid2}>
              <div style={styles.inputRow}>
                <label style={styles.label}>Telegram Bot Token</label>
                <input type="text" style={styles.input} value={telegramToken} onChange={e => setTelegramToken(e.target.value)} placeholder="Enter bot token" />
              </div>
              <div style={styles.inputRow}>
                <label style={styles.label}>Chat ID</label>
                <input type="text" style={styles.input} value={telegramChatId} onChange={e => setTelegramChatId(e.target.value)} placeholder="Enter chat ID" />
              </div>
            </div>
            <div style={{ ...styles.toggleRow, borderBottom: '1px solid var(--border, #30363d)' }}>
              <span style={styles.toggleLabel}>Email Notifications</span>
              <Toggle on={emailNotifs} onClick={() => setEmailNotifs(!emailNotifs)} />
            </div>
            <div style={{ ...styles.toggleRow, borderBottom: '1px solid var(--border, #30363d)' }}>
              <span style={styles.toggleLabel}>Push Notifications</span>
              <Toggle on={pushNotifs} onClick={() => setPushNotifs(!pushNotifs)} />
            </div>
            <div style={{ ...styles.grid2, marginTop: '14px' }}>
              <div style={styles.inputRow}>
                <label style={styles.label}>Quiet Hours Start</label>
                <input type="time" style={styles.input} value={quietStart} onChange={e => setQuietStart(e.target.value)} />
              </div>
              <div style={styles.inputRow}>
                <label style={styles.label}>Quiet Hours End</label>
                <input type="time" style={styles.input} value={quietEnd} onChange={e => setQuietEnd(e.target.value)} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* STRATEGY DEFAULTS */}
      <div style={styles.accordion}>
        <div style={styles.accordionHeader} onClick={() => toggleSection('strategy')}>
          <div style={styles.accordionTitle}>
            <SlidersHorizontal size={18} /> Strategy Defaults
          </div>
          {isOpen('strategy') ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        <div style={styles.accordionBody(isOpen('strategy'))}>
          <div style={styles.accordionContent}>
            <div style={styles.grid2}>
              <div style={styles.inputRow}>
                <label style={styles.label}>Default Symbol</label>
                <input type="text" style={styles.input} value={defaultSymbol} onChange={e => setDefaultSymbol(e.target.value)} />
              </div>
              <div style={styles.inputRow}>
                <label style={styles.label}>Default Timeframe</label>
                <select style={styles.select as React.CSSProperties} value={defaultTimeframe} onChange={e => setDefaultTimeframe(e.target.value)}>
                  <option value="1m">1m</option>
                  <option value="5m">5m</option>
                  <option value="15m">15m</option>
                  <option value="1h">1h</option>
                  <option value="1D">1D</option>
                </select>
              </div>
              <div style={styles.inputRow}>
                <label style={styles.label}>ATR Period</label>
                <input type="number" style={styles.input} value={atrPeriod} onChange={e => setAtrPeriod(e.target.value)} />
              </div>
              <div style={styles.inputRow}>
                <label style={styles.label}>Sensitivity</label>
                <input type="number" step="0.1" style={styles.input} value={sensitivity} onChange={e => setSensitivity(e.target.value)} />
              </div>
            </div>
            <div style={{ ...styles.toggleRow, borderBottom: '1px solid var(--border, #30363d)', marginBottom: '16px' }}>
              <span style={styles.toggleLabel}>Auto-start on deploy</span>
              <Toggle on={autoStart} onClick={() => setAutoStart(!autoStart)} />
            </div>
            <button style={styles.btnPrimary}>
              <Save size={14} /> Save Defaults
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
