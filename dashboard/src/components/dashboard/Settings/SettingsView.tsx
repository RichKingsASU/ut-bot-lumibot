import React, { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Key, Database, Bell, SlidersHorizontal, ChevronDown, ChevronUp, Save, Eye, EyeOff, Send, CheckCircle2, XCircle, Loader2, AlertTriangle, ShieldCheck, ShieldAlert } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'
import { API } from '../../../lib/api'
import { PageHeader } from '../../ui/PageHeader'
import { tradingModeBadgeStyle, parsePaperMode } from '../../../hooks/useTradingMode'
import { getAdminKey, setAdminKey, netlifyFetch } from '../../../lib/apiClient'

const PAPER_URL = 'https://paper-api.alpaca.markets'
const LIVE_URL = 'https://api.alpaca.markets'

/** Mask a broker key for display on reload — never render the full value. */
function maskKey(k: string): string {
  if (!k) return ''
  const trimmed = k.trim()
  if (trimmed.length <= 6) return trimmed.slice(0, 2) + '•••••'
  return trimmed.slice(0, 2) + '•'.repeat(6) + trimmed.slice(-4)
}

type SaveStatus = { ok: boolean; msg: string } | null

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

type Section = 'admin' | 'broker' | 'database' | 'notifications' | 'strategy'

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
        <button
          style={styles.eyeBtn}
          onClick={() => setVisible(!visible)}
          aria-label={visible ? 'Hide value' : 'Show value'}
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </div>
  )
}

export function SettingsView() {
  const [openSections, setOpenSections] = useState<Set<Section>>(new Set(['admin']))
  // Admin API Key
  const [adminKeyInput, setAdminKeyInput] = useState('')
  const [adminKeyMasked, setAdminKeyMasked] = useState('')
  const [adminKeyHasValue, setAdminKeyHasValue] = useState(false)
  const [adminKeyTestLoading, setAdminKeyTestLoading] = useState(false)
  const [adminKeySaveStatus, setAdminKeySaveStatus] = useState<SaveStatus>(null)
  const [adminKeyTestStatus, setAdminKeyTestStatus] = useState<null | 'success' | 'error'>(null)
  const [adminKeyTestMsg, setAdminKeyTestMsg] = useState('')

  const [alpacaKey, setAlpacaKey] = useState('')
  const [alpacaSecret, setAlpacaSecret] = useState('')
  const [paperMode, setPaperMode] = useState(true)
  // Badge/toggle both reflect the persisted-then-local paperMode so they never disagree.
  const modeBadge = tradingModeBadgeStyle(paperMode ? 'paper' : 'live')
  const [hasStoredKey, setHasStoredKey] = useState(false)
  const [hasStoredSecret, setHasStoredSecret] = useState(false)
  const [storedKeyMask, setStoredKeyMask] = useState('')
  const [savingBroker, setSavingBroker] = useState(false)
  const [brokerSaveStatus, setBrokerSaveStatus] = useState<SaveStatus>(null)
  const [supabaseUrl] = useState('https://supabase.com/dashboard/project/wnigkahkamoizjpmpuxs')
  const [supabaseKey, setSupabaseKey] = useState('')
  const [dbConnected, setDbConnected] = useState<boolean | null>(null)
  const [testingDb, setTestingDb] = useState(false)
  const [telegramToken, setTelegramToken] = useState('')
  const [telegramChatId, setTelegramChatId] = useState('')
  const [telegramSaveStatus, setTelegramSaveStatus] = useState<SaveStatus>(null)
  const [emailNotifs, setEmailNotifs] = useState(false)
  const [pushNotifs, setPushNotifs] = useState(true)
  const [quietStart, setQuietStart] = useState('22:00')
  const [quietEnd, setQuietEnd] = useState('07:00')
  const [defaultSymbol, setDefaultSymbol] = useState('IWM')
  const [defaultTimeframe, setDefaultTimeframe] = useState('15m')
  const [atrPeriod, setAtrPeriod] = useState('14')
  const [sensitivity, setSensitivity] = useState('2.0')
  const [autoStart, setAutoStart] = useState(false)

  // Connection Testing States
  const [testLoading, setTestLoading] = useState(false)
  const [testStatus, setTestStatus] = useState<null | 'success' | 'error'>(null)
  const [testMessage, setTestMessage] = useState('')
  const [testLatency, setTestLatency] = useState<number | null>(null)
  const [lastVerified, setLastVerified] = useState<string | null>(null)
  const [accountData, setAccountData] = useState<any>(null)

  useEffect(() => {
    const existing = getAdminKey()
    if (existing) {
      setAdminKeyHasValue(true)
      setAdminKeyMasked(existing.slice(0, 4) + '•'.repeat(Math.max(0, existing.length - 4)))
    }
  }, [])

  const handleSaveAdminKey = () => {
    const val = adminKeyInput.trim()
    if (!val) {
      setAdminKeySaveStatus({ ok: false, msg: 'Enter a key value before saving.' })
      setTimeout(() => setAdminKeySaveStatus(null), 4000)
      return
    }
    setAdminKey(val)
    setAdminKeyHasValue(true)
    setAdminKeyMasked(val.slice(0, 4) + '•'.repeat(Math.max(0, val.length - 4)))
    setAdminKeyInput('')
    setAdminKeySaveStatus({ ok: true, msg: 'Admin API Key saved.' })
    setTimeout(() => setAdminKeySaveStatus(null), 4000)
  }

  const handleTestAdminKey = async () => {
    if (adminKeyTestLoading) return
    // If the user has typed a key but hasn't saved it yet, save it first so the
    // test uses the current input value rather than a stale/empty stored value.
    const pendingInput = adminKeyInput.trim()
    if (pendingInput) {
      setAdminKey(pendingInput)
      setAdminKeyHasValue(true)
      setAdminKeyMasked(pendingInput.slice(0, 4) + '•'.repeat(Math.max(0, pendingInput.length - 4)))
      setAdminKeyInput('')
    }
    if (!getAdminKey() && !pendingInput) {
      setAdminKeyTestStatus('error')
      setAdminKeyTestMsg('Enter an Admin API Key before testing.')
      return
    }
    setAdminKeyTestLoading(true)
    setAdminKeyTestStatus(null)
    try {
      const res = await netlifyFetch('alpaca-account')
      if (res.ok) {
        setAdminKeyTestStatus('success')
        setAdminKeyTestMsg('Connection verified — admin key is valid.')
      } else {
        setAdminKeyTestStatus('error')
        let data: any = {}
        try { data = await res.json() } catch(e) {}
        if (data.code === 'ADMIN_UNAUTHORIZED') {
          setAdminKeyTestMsg('Invalid or missing admin key — check the value and try again.')
        } else if (res.status === 401) {
          setAdminKeyTestMsg(`Admin key accepted, but Alpaca returned 401: ${data.error || 'Check Alpaca keys.'}`)
        } else {
          setAdminKeyTestMsg(`Error: ${data.error || res.status}`)
        }
      }
    } catch (e) {
      setAdminKeyTestStatus('error')
      setAdminKeyTestMsg('Network error — check connection.')
    } finally {
      setAdminKeyTestLoading(false)
    }
  }

  const handleClearAdminKey = () => {
    localStorage.removeItem('ADMIN_API_KEY')
    localStorage.removeItem('admin_api_key')
    setAdminKeyHasValue(false)
    setAdminKeyMasked('')
    setAdminKeyInput('')
    setAdminKeySaveStatus({ ok: true, msg: 'Admin API Key cleared.' })
    setTimeout(() => setAdminKeySaveStatus(null), 4000)
  }

  useEffect(() => {
    const saved = localStorage.getItem('alpaca_last_verified')
    if (saved) setLastVerified(saved)

    // Telegram config
    supabase
      .from('user_settings')
      .select('value')
      .eq('key', 'telegram_config')
      .maybeSingle()
      .then(({ data }) => {
        if (data?.value) {
          try {
            const cfg = typeof data.value === 'string' ? JSON.parse(data.value) : data.value
            setTelegramToken(cfg.token || '')
            setTelegramChatId(cfg.chatId || '')
          } catch { /* ignore parse errors */ }
        }
      })

    // Trading mode — the toggle's source of truth is Supabase, not React state.
    supabase
      .from('user_settings')
      .select('value')
      .eq('key', 'paper_mode')
      .maybeSingle()
      .then(({ data }) => {
        const paper = parsePaperMode(data?.value)
        // Default to the safe (paper) mode when unset or unparseable.
        setPaperMode(paper !== false)
      })

    // Broker credentials — load masked. Never populate the inputs with the
    // real secret; only record that a value exists so blank = "unchanged".
    supabase
      .from('user_settings')
      .select('value')
      .eq('key', 'broker_credentials')
      .maybeSingle()
      .then(({ data }) => {
        if (!data?.value) return
        try {
          const cfg = typeof data.value === 'string' ? JSON.parse(data.value) : data.value
          if (cfg?.api_key) {
            setHasStoredKey(true)
            setStoredKeyMask(maskKey(String(cfg.api_key)))
          }
          if (cfg?.api_secret) setHasStoredSecret(true)
        } catch { /* ignore parse errors */ }
      })
  }, [])

  const handleSaveTelegram = async () => {
    const { error } = await supabase
      .from('user_settings')
      .upsert(
        {
          key: 'telegram_config',
          value: JSON.stringify({ token: telegramToken, chatId: telegramChatId }),
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'key' }
      )
    if (error) {
      setTelegramSaveStatus({ ok: false, msg: error.message || 'Save failed — check connection/permissions.' })
    } else {
      setTelegramSaveStatus({ ok: true, msg: 'Telegram config saved.' })
    }
    setTimeout(() => setTelegramSaveStatus(null), 5000)
  }

  const handleSaveBroker = async () => {
    if (savingBroker) return
    setBrokerSaveStatus(null)

    const keyProvided = alpacaKey.trim().length > 0
    const secretProvided = alpacaSecret.trim().length > 0

    // Blank means "unchanged" only if a value is already stored; otherwise required.
    if (!keyProvided && !hasStoredKey) {
      setBrokerSaveStatus({ ok: false, msg: 'Alpaca API Key is required.' })
      return
    }
    if (!secretProvided && !hasStoredSecret) {
      setBrokerSaveStatus({ ok: false, msg: 'Alpaca Secret Key is required.' })
      return
    }

    setSavingBroker(true)
    const baseUrl = paperMode ? PAPER_URL : LIVE_URL

    try {
      // 1. Persist trading mode + base URL (the running fleet consumes these via
      //    env/runtime_config at startup; this store keeps the dashboard coherent
      //    and refresh-safe, and the useTradingMode badge in sync).
      const { error: modeError } = await supabase
        .from('user_settings')
        .upsert(
          {
            key: 'paper_mode',
            value: { paper_mode: paperMode, base_url: baseUrl },
            updated_at: new Date().toISOString(),
          },
          { onConflict: 'key' }
        )
      if (modeError) throw modeError

      // 2. Persist credentials — only overwrite the field the user actually
      //    changed. A blank field preserves the previously stored value.
      if (keyProvided || secretProvided) {
        const { data: existing } = await supabase
          .from('user_settings')
          .select('value')
          .eq('key', 'broker_credentials')
          .maybeSingle()
        const prev = (existing?.value && typeof existing.value === 'object' ? existing.value : {}) as {
          api_key?: string
          api_secret?: string
        }
        const creds = {
          api_key: keyProvided ? alpacaKey.trim() : prev.api_key,
          api_secret: secretProvided ? alpacaSecret.trim() : prev.api_secret,
        }
        const { error: credError } = await supabase
          .from('user_settings')
          .upsert(
            { key: 'broker_credentials', value: creds, updated_at: new Date().toISOString() },
            { onConflict: 'key' }
          )
        if (credError) throw credError

        // Reflect stored state as masked; clear the plaintext inputs.
        if (creds.api_key) {
          setHasStoredKey(true)
          setStoredKeyMask(maskKey(creds.api_key))
        }
        if (creds.api_secret) setHasStoredSecret(true)
        setAlpacaKey('')
        setAlpacaSecret('')
      }

      setBrokerSaveStatus({ ok: true, msg: `Broker config saved — ${paperMode ? 'Paper' : 'Live'} mode.` })
    } catch (err: any) {
      setBrokerSaveStatus({ ok: false, msg: err?.message || 'Save failed — check connection/permissions.' })
    } finally {
      setSavingBroker(false)
      setTimeout(() => setBrokerSaveStatus(null), 6000)
    }
  }

  const handleTestDb = async () => {
    setTestingDb(true)
    try {
      const { error } = await supabase.from('user_settings').select('id').limit(1)
      setDbConnected(!error)
    } catch (e) {
      console.error('DB Test Failed:', e)
      setDbConnected(false)
    } finally {
      setTestingDb(false)
    }
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
      const response = await netlifyFetch('alpaca-account', {
        method: 'POST',
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

      {/* ADMIN API KEY */}
      <div style={styles.accordion}>
        <div style={styles.accordionHeader} onClick={() => toggleSection('admin')}>
          <div style={styles.accordionTitle}>
            <ShieldAlert size={18} /> Admin API Key
          </div>
          {isOpen('admin') ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
        <div style={styles.accordionBody(isOpen('admin'))}>
          <div style={styles.accordionContent}>
            <p style={{ ...styles.muted, marginBottom: '14px' }}>
              Required for all Netlify function calls (market data, pipeline status, live alerts).
              {adminKeyHasValue && (
                <span style={{ color: 'var(--green, #3fb950)', marginLeft: '8px' }}>
                  <CheckCircle2 size={13} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />
                  Key configured: {adminKeyMasked}
                </span>
              )}
            </p>
            <div style={styles.inputRow}>
              <label style={styles.label}>Admin API Key</label>
              <MaskedInput
                label=""
                value={adminKeyInput}
                onChange={setAdminKeyInput}
                placeholder={adminKeyHasValue ? 'Leave blank to keep existing key' : 'Enter admin API key'}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' as const, marginTop: '8px' }}>
              <button style={styles.btnPrimary} onClick={handleSaveAdminKey}>
                <Save size={14} /> Save Key
              </button>
              <button
                style={{ ...styles.btn, opacity: adminKeyTestLoading ? 0.6 : 1 }}
                onClick={handleTestAdminKey}
                disabled={adminKeyTestLoading}
              >
                {adminKeyTestLoading ? <Loader2 size={14} /> : null}
                {adminKeyTestLoading ? 'Testing...' : 'Test Connection'}
              </button>
              {adminKeyHasValue && (
                <button
                  style={{ ...styles.btn, color: 'var(--red, #f85149)', borderColor: 'rgba(248,81,73,0.3)' }}
                  onClick={handleClearAdminKey}
                >
                  Clear Key
                </button>
              )}
              {adminKeySaveStatus && (
                <span style={{ fontSize: '13px', color: adminKeySaveStatus.ok ? 'var(--green, #3fb950)' : 'var(--red, #f85149)', display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  {adminKeySaveStatus.ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                  {adminKeySaveStatus.msg}
                </span>
              )}
            </div>
            {adminKeyTestStatus && (
              <div style={{ ...styles.testResult, ...(adminKeyTestStatus === 'success' ? styles.successBox : styles.errorBox), marginTop: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
                  {adminKeyTestStatus === 'success' ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
                  {adminKeyTestStatus === 'success' ? 'Key Valid' : 'Key Invalid'}
                </div>
                <div style={{ fontSize: '13px', opacity: 0.9 }}>{adminKeyTestMsg}</div>
              </div>
            )}
          </div>
        </div>
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
              <MaskedInput
                label="Alpaca API Key"
                value={alpacaKey}
                onChange={setAlpacaKey}
                placeholder={hasStoredKey ? `Stored: ${storedKeyMask} — leave blank to keep` : 'AKXXXXXXXXXXXXXXXXXX'}
              />
              <MaskedInput
                label="Alpaca Secret Key"
                value={alpacaSecret}
                onChange={setAlpacaSecret}
                placeholder={hasStoredSecret ? 'Stored — leave blank to keep' : 'Enter secret key'}
              />
            </div>
            <div style={styles.inputRow}>
              <label style={styles.label}>Base URL</label>
              <input
                type="text"
                style={{ ...styles.input, opacity: 0.7 }}
                value={paperMode ? PAPER_URL : LIVE_URL}
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
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase' as const,
                      backgroundColor: modeBadge.background,
                      color: modeBadge.color,
                      border: modeBadge.border,
                      marginLeft: '8px',
                    }}
                  >
                    {modeBadge.label}
                  </span>
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

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
              <button
                style={{
                  ...styles.btnPrimary,
                  opacity: savingBroker ? 0.6 : 1,
                  cursor: savingBroker ? 'not-allowed' : 'pointer',
                }}
                onClick={handleSaveBroker}
                disabled={savingBroker}
              >
                {savingBroker ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                {savingBroker ? 'Saving...' : 'Save Broker Config'}
              </button>
              {brokerSaveStatus && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '13px',
                    color: brokerSaveStatus.ok ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                  }}
                >
                  {brokerSaveStatus.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                  {brokerSaveStatus.msg}
                </span>
              )}
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
              <label style={styles.label}>Database endpoint (<a href={supabaseUrl} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--blue)' }}>Open Dashboard</a>)</label>
              <input type="text" style={{ ...styles.input, opacity: 0.7 }} value={supabaseUrl} readOnly />
            </div>
            <MaskedInput label="Database token" value={supabaseKey} onChange={setSupabaseKey} placeholder="Enter database token" />
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '8px' }}>
              <button 
                style={{
                  ...styles.btn,
                  opacity: testingDb ? 0.7 : 1,
                  cursor: testingDb ? 'not-allowed' : 'pointer'
                }} 
                onClick={handleTestDb}
                disabled={testingDb}
              >
                {testingDb ? 'Testing...' : 'Test Connection'}
              </button>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <span style={styles.statusDot(dbConnected === true)} />
                <span style={{ fontSize: '13px', color: dbConnected === true ? 'var(--green, #3fb950)' : (dbConnected === false ? 'var(--red, #f85149)' : 'var(--text-muted, #8b949e)') }}>
                  {dbConnected === true ? 'Connected' : (dbConnected === false ? 'Failed' : 'Disconnected')}
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
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '12px',
                    color: telegramSaveStatus.ok ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
                  }}>
                    {telegramSaveStatus.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                    {telegramSaveStatus.msg}
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
