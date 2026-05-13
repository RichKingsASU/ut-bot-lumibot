import React, { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Key, Database, Bell, SlidersHorizontal, ChevronDown, ChevronUp, Save, Eye, EyeOff, Send, CheckCircle2, XCircle, Loader2, AlertTriangle, ShieldCheck } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'
import { API } from '../../../lib/api'
import { PageHeader } from '../../ui/PageHeader'

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
    maxHeight: open ? '800px' : '0',
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
  testResult: {
    marginTop: '16px',
    padding: '12px 16px',
    borderRadius: '8px',
    display: 'flex' as const,
    flexDirection: 'column' as const,
    gap: '8px',
    fontSize: '14px',
    border: '1px solid transparent',
  },
  successBox: {
    backgroundColor: 'rgba(63, 185, 80, 0.1)',
    borderColor: 'rgba(63, 185, 80, 0.2)',
    color: '#3fb950',
  },
  errorBox: {
    backgroundColor: 'rgba(248, 81, 73, 0.1)',
    borderColor: 'rgba(248, 81, 73, 0.2)',
    color: '#f85149',
  },
  badge: (paper: boolean) => ({
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    backgroundColor: paper ? 'rgba(63, 185, 80, 0.2)' : 'rgba(248, 81, 73, 0.2)',
    color: paper ? '#3fb950' : '#f85149',
    marginLeft: '8px',
  }),
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
  const [telegramSaveStatus, setTelegramSaveStatus] = useState<'saved' | 'error' | null>(null)
  const [emailNotifs, setEmailNotifs] = useState(false)
  const [pushNotifs, setPushNotifs] = useState(true)
  const [quietStart, setQuietStart] = useState('22:00')
  const [quietEnd, setQuietEnd] = useState('07:00')
  const [defaultSymbol, setDefaultSymbol] = useState('IWM')
  const [defaultTimeframe, setDefaultTimeframe] = useState('1m')
  const [atrPeriod, setAtrPeriod] = useState('10')
  const [sensitivity, setSensitivity] = useState('1.0')
  const [autoStart, setAutoStart] = useState(false)

  // Connection Testing States
  const [testLoading, setTestLoading] = useState(false)
  const [testStatus, setTestStatus] = useState<null | 'success' | 'error'>(null)
  const [testMessage, setTestMessage] = useState('')
  const [testLatency, setTestLatency] = useState<number | null>(null)
  const [lastVerified, setLastVerified] = useState<string | null>(null)
  const [accountData, setAccountData] = useState<any>(null)

  useEffect(() => {
    const saved = localStorage.getItem('alpaca_last_verified')
    if (saved) setLastVerified(saved)

    supabase
      .from('user_settings')
      .select('value')
      .eq('key', 'telegram_config')
      .single()
      .then(({ data }) => {
        if (data?.value) {
          try {
            const cfg = typeof data.value === 'string' ? JSON.parse(data.value) : data.value
            setTelegramToken(cfg.token || '')
            setTelegramChatId(cfg.chatId || '')
          } catch { /* ignore parse errors */ }
        }
      })
  }, [])

  const handleSaveTelegram = async () => {
    const { error } = await supabase
      .from('user_settings')
      .upsert({
        key: 'telegram_config',
        value: JSON.stringify({ token: telegramToken, chatId: telegramChatId })
      })
    setTelegramSaveStatus(error ? 'error' : 'saved')
    setTimeout(() => setTelegramSaveStatus(null), 3000)
  }

  const handleTestAlpaca = async () => {
    if (testLoading) return
    
    const baseUrl = paperMode ? 'https://paper-api.alpaca.markets' : 'https://api.alpaca.markets'
    
    if (!alpacaKey || !alpacaSecret) {
      setTestStatus('error')
      setTestMessage('API Key and Secret Key are required')
      return
    }

    if (!paperMode) {
      const confirmLive = window.confirm(
        'CRITICAL SAFETY CHECK: You are about to test a LIVE Alpaca connection.\n\n' +
        'This will verify real account credentials. Continue?'
      )
      if (!confirmLive) return
    }

    setTestLoading(true)
    setTestStatus(null)
    setTestMessage('')

    try {
      console.log(`[CONN_TEST] Attempting connection to ${baseUrl}...`)
      const response = await fetch(API.alpacaAccount(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-admin-api-key': 'test-admin-key' // In a real app, this would be a secure session key
        },
        body: JSON.stringify({
          apiKey: alpacaKey,
          apiSecret: alpacaSecret,
          baseUrl: baseUrl
        })
      })

      const data = await response.json()

      if (response.ok) {
        console.log('[CONN_TEST] Success:', {
          status: data.status,
          latency: data.latency,
          isPaper: data.isPaper
        })
        setTestStatus('success')
        const now = new Date().toLocaleString()
        setTestMessage(`Successfully connected to Alpaca ${data.isPaper ? 'Paper' : 'Live'} Trading`)
        setTestLatency(data.latency)
        setAccountData(data)
        setLastVerified(now)
        localStorage.setItem('alpaca_last_verified', now)
      } else {
        console.error('[CONN_TEST] Failure:', data.error)
        setTestStatus('error')
        setTestMessage(data.error || 'Unknown connection error')
        setTestLatency(data.latency || null)
      }
    } catch (err) {
      console.error('[CONN_TEST] Exception:', err)
      setTestStatus('error')
      setTestMessage('Network error: Could not reach validation server')
    } finally {
      setTestLoading(false)
    }
  }

  const handleTestTelegram = async () => {
    try {
      await fetch(
        `https://api.telegram.org/bot${telegramToken}/sendMessage`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: telegramChatId,
            text: 'Disrupting Alpha — Test message. Telegram alerts are working.'
          })
        }
      )
    } catch (e) {
      console.error('Telegram test failed:', e)
    }
  }

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
      <PageHeader title="Settings" subtitle="Broker · Database · Bot" />

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
              <button 
                style={{
                  ...styles.btn,
                  opacity: testLoading ? 0.6 : 1,
                  cursor: testLoading ? 'not-allowed' : 'pointer'
                }} 
                onClick={handleTestAlpaca}
                disabled={testLoading}
              >
                {testLoading ? (
                  <><Loader2 size={14} className="animate-spin" /> Testing...</>
                ) : (
                  'Test Connection'
                )}
              </button>
              <div style={styles.toggleRow}>
                <span style={{ ...styles.toggleLabel, marginRight: '10px' }}>
                  {paperMode ? 'Paper Mode' : 'Live Mode'}
                  <span style={styles.badge(paperMode)}>{paperMode ? 'Paper' : 'Live'}</span>
                </span>
                <Toggle on={!paperMode} onClick={() => {
                  if (paperMode) {
                    const confirmed = window.confirm(
                      'WARNING: SWITCHING TO LIVE TRADING\n\n' +
                      'This will use real capital from your Alpaca account.\n' +
                      'All orders will be REAL and cannot be undone.\n\n' +
                      'Are you absolutely sure?'
                    )
                    if (!confirmed) return
                  }
                  setPaperMode(!paperMode)
                  setTestStatus(null) // Reset test status on mode change
                }} />
              </div>
            </div>

            {testStatus && (
              <div style={{
                ...styles.testResult,
                ...(testStatus === 'success' ? styles.successBox : styles.errorBox)
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                  {testStatus === 'success' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  {testStatus === 'success' ? 'Connection Verified' : 'Connection Failed'}
                </div>
                <div style={{ fontSize: '13px', opacity: 0.9 }}>
                  {testMessage}
                </div>
                {testStatus === 'success' && accountData && (
                  <div style={{ 
                    marginTop: '4px', 
                    padding: '8px', 
                    backgroundColor: 'rgba(255,255,255,0.05)', 
                    borderRadius: '4px',
                    fontSize: '12px',
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '4px'
                  }}>
                    <div>Status: <span style={{ fontWeight: 600 }}>{accountData.status}</span></div>
                    <div>Latency: <span style={{ fontWeight: 600 }}>{testLatency}ms</span></div>
                    <div>Account #: <span style={{ fontWeight: 600 }}>{accountData.account_number}</span></div>
                    <div>Environment: <span style={{ fontWeight: 600 }}>{accountData.isPaper ? 'Paper' : 'Live'}</span></div>
                  </div>
                )}
                {lastVerified && (
                  <div style={{ fontSize: '11px', opacity: 0.6, marginTop: '4px' }}>
                    Last verified: {lastVerified}
                  </div>
                )}
              </div>
            )}

            {!paperMode && (
              <div style={{
                marginTop: '12px',
                padding: '10px 14px',
                borderRadius: '6px',
                backgroundColor: 'rgba(248, 81, 73, 0.1)',
                border: '1px solid rgba(248, 81, 73, 0.2)',
                color: '#f85149',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                fontSize: '12px'
              }}>
                <AlertTriangle size={16} style={{ marginTop: '2px', flexShrink: 0 }} />
                <div>
                  <strong style={{ display: 'block', marginBottom: '2px' }}>LIVE TRADING ACTIVE</strong>
                  Your strategy will execute real trades with real capital. Ensure your risk settings are strictly validated.
                </div>
              </div>
            )}
            {paperMode && testStatus === 'success' && (
              <div style={{
                marginTop: '12px',
                padding: '10px 14px',
                borderRadius: '6px',
                backgroundColor: 'rgba(63, 185, 80, 0.1)',
                border: '1px solid rgba(63, 185, 80, 0.2)',
                color: '#3fb950',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '12px'
              }}>
                <ShieldCheck size={16} />
                <span>Safely connected to Paper Trading environment.</span>
              </div>
            )}
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
            {/* Telegram Bot Configuration */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <svg style={{ width: '14px', height: '14px', color: 'var(--text-muted, #8b949e)' }} viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8l-1.68 7.92c-.12.56-.46.7-.94.44l-2.6-1.92-1.26 1.22c-.14.14-.26.26-.52.26l.18-2.62 4.74-4.28c.2-.18-.04-.28-.32-.1L7.46 14.3l-2.56-.8c-.56-.18-.58-.56.12-.82l10-3.86c.46-.16.88.1.62.98z"/>
                </svg>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted, #8b949e)', textTransform: 'uppercase' as const, letterSpacing: '0.5px' }}>
                  Telegram Bot
                </span>
              </div>
              <div style={styles.grid2}>
                <div style={styles.inputRow}>
                  <label style={styles.label}>Bot Token</label>
                  <input
                    type="password"
                    style={styles.input}
                    value={telegramToken}
                    onChange={e => setTelegramToken(e.target.value)}
                    placeholder="Enter Telegram bot token"
                  />
                </div>
                <div style={styles.inputRow}>
                  <label style={styles.label}>Chat ID</label>
                  <input
                    type="text"
                    style={styles.input}
                    value={telegramChatId}
                    onChange={e => setTelegramChatId(e.target.value)}
                    placeholder="Enter Chat ID"
                  />
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <button style={styles.btnPrimary} onClick={handleSaveTelegram}>
                  <Save size={14} /> Save Telegram Config
                </button>
                <button
                  style={{
                    ...styles.btn,
                    opacity: (!telegramToken || !telegramChatId) ? 0.4 : 1,
                    cursor: (!telegramToken || !telegramChatId) ? 'not-allowed' : 'pointer',
                  }}
                  onClick={handleTestTelegram}
                  disabled={!telegramToken || !telegramChatId}
                >
                  <Send size={14} /> Send Test Message
                </button>
                {telegramSaveStatus && (
                  <span style={{
                    fontSize: '12px',
                    color: telegramSaveStatus === 'saved' ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                  }}>
                    {telegramSaveStatus === 'saved' ? 'Saved' : 'Failed'}
                  </span>
                )}
              </div>
            </div>

            {/* Divider between Telegram and other notifications */}
            <div style={{ borderTop: '1px solid var(--border, #30363d)', marginBottom: '16px' }} />

            {/* Email / Push / Quiet Hours */}
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
