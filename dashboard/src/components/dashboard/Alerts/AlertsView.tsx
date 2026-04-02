import React, { useState } from 'react'
import { Bell, Send, MessageSquare, ToggleLeft, ToggleRight, Filter, CheckCircle, XCircle } from 'lucide-react'

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
  section: {
    backgroundColor: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '8px',
    padding: '20px',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '16px',
    fontWeight: 600,
    marginBottom: '16px',
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '8px',
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
  btn: {
    padding: '8px 16px',
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
  toggleRow: {
    display: 'flex' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    padding: '12px 0',
    borderBottom: '1px solid var(--border, #30363d)',
  },
  toggleLabel: {
    fontWeight: 500,
    fontSize: '14px',
  },
  toggleDesc: {
    fontSize: '12px',
    color: 'var(--text-muted, #8b949e)',
    marginTop: '2px',
  },
  toggleGrid: {
    display: 'grid' as const,
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '0 24px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: '13px',
  },
  th: {
    textAlign: 'left' as const,
    padding: '10px 12px',
    borderBottom: '1px solid var(--border, #30363d)',
    color: 'var(--text-muted, #8b949e)',
    fontWeight: 600,
    fontSize: '12px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  td: {
    padding: '10px 12px',
    borderBottom: '1px solid var(--border, #30363d)',
  },
  typeBadge: (type: string) => ({
    padding: '2px 8px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 600,
    backgroundColor: type === 'Buy Signal' ? 'rgba(63,185,80,0.15)' :
      type === 'Sell Signal' ? 'rgba(248,81,73,0.15)' :
      type === 'Drawdown' ? 'rgba(227,179,65,0.15)' :
      'rgba(88,166,255,0.12)',
    color: type === 'Buy Signal' ? 'var(--green, #3fb950)' :
      type === 'Sell Signal' ? 'var(--red, #f85149)' :
      type === 'Drawdown' ? 'var(--amber, #e3b341)' :
      'var(--blue, #58a6ff)',
  }),
  muted: {
    color: 'var(--text-muted, #8b949e)',
    fontSize: '13px',
  },
  toast: {
    position: 'fixed' as const,
    bottom: '24px',
    right: '24px',
    backgroundColor: 'var(--green, #3fb950)',
    color: '#0d1117',
    padding: '12px 20px',
    borderRadius: '8px',
    fontWeight: 600,
    fontSize: '14px',
    zIndex: 1000,
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
  },
  select: {
    padding: '6px 10px',
    borderRadius: '6px',
    border: '1px solid var(--border, #30363d)',
    backgroundColor: 'var(--bg-tertiary, #21262d)',
    color: 'var(--text-primary, #e6edf3)',
    fontSize: '13px',
    outline: 'none',
  },
}

const alertToggles = [
  { key: 'buy', label: 'Buy Signals', desc: 'Alert when a buy signal is generated' },
  { key: 'sell', label: 'Sell Signals', desc: 'Alert when a sell signal is generated' },
  { key: 'posOpen', label: 'Position Opened', desc: 'Alert when a new position is opened' },
  { key: 'posClose', label: 'Position Closed', desc: 'Alert when a position is closed' },
  { key: 'dailyPnl', label: 'Daily P&L Summary', desc: 'End-of-day profit and loss summary' },
  { key: 'drawdown', label: 'Drawdown Warning', desc: 'Alert when drawdown exceeds threshold' },
  { key: 'botStatus', label: 'Bot Status Change', desc: 'Alert when bot starts, stops, or errors' },
  { key: 'connLost', label: 'Connection Lost', desc: 'Alert on data feed or broker disconnection' },
]

const mockAlerts = [
  { time: '2026-04-02 09:36:30', type: 'Daily P&L', message: 'Daily P&L: +$342.18 (+1.12%)', delivered: true },
  { time: '2026-04-02 09:35:02', type: 'Buy Signal', message: 'BUY IWM @ 204.35 | Strength: 0.82', delivered: true },
  { time: '2026-04-02 09:33:05', type: 'Drawdown', message: 'Drawdown warning: -2.4% from peak', delivered: true },
  { time: '2026-04-02 09:31:01', type: 'Buy Signal', message: 'BUY SPY @ 512.80 | Strength: 0.76', delivered: true },
  { time: '2026-04-02 09:30:18', type: 'Connection', message: 'OPRA options feed connection lost', delivered: false },
  { time: '2026-04-02 09:30:02', type: 'Bot Status', message: 'Bot Engine started successfully', delivered: true },
  { time: '2026-04-01 16:00:01', type: 'Daily P&L', message: 'Daily P&L: -$127.54 (-0.42%)', delivered: true },
  { time: '2026-04-01 15:45:00', type: 'Sell Signal', message: 'SELL QQQ @ 438.20 | Strength: 0.71', delivered: true },
  { time: '2026-04-01 14:22:10', type: 'Sell Signal', message: 'SELL IWM @ 203.10 | Strength: 0.68', delivered: true },
  { time: '2026-04-01 10:15:30', type: 'Buy Signal', message: 'BUY IWM @ 202.50 | Strength: 0.88', delivered: true },
]

const defaultToggles: Record<string, boolean> = {
  buy: true, sell: true, posOpen: true, posClose: false,
  dailyPnl: true, drawdown: true, botStatus: true, connLost: true,
}

export function AlertsView() {
  const [botToken, setBotToken] = useState('')
  const [chatId, setChatId] = useState('')
  const [telegramEnabled, setTelegramEnabled] = useState(false)
  const [toggles, setToggles] = useState(defaultToggles)
  const [showToast, setShowToast] = useState(false)
  const [filterType, setFilterType] = useState('All')

  const handleTest = () => {
    setShowToast(true)
    setTimeout(() => setShowToast(false), 3000)
  }

  const handleToggle = (key: string) => {
    setToggles(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const filteredAlerts = filterType === 'All' ? mockAlerts : mockAlerts.filter(a => a.type === filterType)
  const alertTypes = ['All', ...Array.from(new Set(mockAlerts.map(a => a.type)))]

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <Bell size={22} />
        Alerts Management
      </div>

      {/* Telegram Configuration */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <MessageSquare size={18} /> Telegram Configuration
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
          <div>
            <label style={styles.label}>Bot Token</label>
            <input
              type="password"
              style={styles.input}
              placeholder="Enter Telegram bot token"
              value={botToken}
              onChange={e => setBotToken(e.target.value)}
            />
          </div>
          <div>
            <label style={styles.label}>Chat ID</label>
            <input
              type="text"
              style={styles.input}
              placeholder="Enter Chat ID"
              value={chatId}
              onChange={e => setChatId(e.target.value)}
            />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button style={styles.btn} onClick={handleTest}>
            <Send size={14} /> Test Message
          </button>
          <div
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}
            onClick={() => setTelegramEnabled(!telegramEnabled)}
          >
            {telegramEnabled ? (
              <ToggleRight size={28} style={{ color: 'var(--green, #3fb950)' }} />
            ) : (
              <ToggleLeft size={28} style={{ color: 'var(--text-muted, #8b949e)' }} />
            )}
            <span style={{ fontSize: '13px', fontWeight: 500, color: telegramEnabled ? 'var(--green, #3fb950)' : 'var(--text-muted, #8b949e)' }}>
              {telegramEnabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        </div>
      </div>

      {/* Alert Toggles */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <Bell size={18} /> Alert Toggles
        </div>
        <div style={styles.toggleGrid}>
          {alertToggles.map(toggle => (
            <div key={toggle.key} style={styles.toggleRow}>
              <div>
                <div style={styles.toggleLabel}>{toggle.label}</div>
                <div style={styles.toggleDesc}>{toggle.desc}</div>
              </div>
              <div style={{ cursor: 'pointer' }} onClick={() => handleToggle(toggle.key)}>
                {toggles[toggle.key] ? (
                  <ToggleRight size={26} style={{ color: 'var(--green, #3fb950)' }} />
                ) : (
                  <ToggleLeft size={26} style={{ color: 'var(--text-muted, #8b949e)' }} />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Alert History */}
      <div style={styles.section}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={styles.sectionTitle}>
            <Filter size={18} /> Alert History
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={styles.muted}>Filter by type:</span>
            <select style={styles.select} value={filterType} onChange={e => setFilterType(e.target.value)}>
              {alertTypes.map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Time</th>
              <th style={styles.th}>Type</th>
              <th style={styles.th}>Message</th>
              <th style={{ ...styles.th, textAlign: 'center' as const }}>Delivered</th>
            </tr>
          </thead>
          <tbody>
            {filteredAlerts.map((alert, i) => (
              <tr key={i}>
                <td style={{ ...styles.td, fontFamily: 'monospace', color: 'var(--text-muted, #8b949e)', whiteSpace: 'nowrap' as const }}>{alert.time}</td>
                <td style={styles.td}>
                  <span style={styles.typeBadge(alert.type)}>{alert.type}</span>
                </td>
                <td style={styles.td}>{alert.message}</td>
                <td style={{ ...styles.td, textAlign: 'center' as const }}>
                  {alert.delivered ? (
                    <CheckCircle size={16} style={{ color: 'var(--green, #3fb950)' }} />
                  ) : (
                    <XCircle size={16} style={{ color: 'var(--red, #f85149)' }} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showToast && (
        <div style={styles.toast}>
          <CheckCircle size={16} style={{ verticalAlign: 'middle', marginRight: '8px' }} />
          Message sent!
        </div>
      )}
    </div>
  )
}
