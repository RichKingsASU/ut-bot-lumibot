import React, { useState } from 'react'
import { Database, Cloud, Activity, RefreshCw, Table, ScrollText, Wifi } from 'lucide-react'
import { useBotStatus } from '../../../hooks/useBotStatus'
import { PageHeader } from '../../ui/PageHeader'

const styles = {
  container: {
    padding: '24px',
    backgroundColor: 'var(--bg-primary, #0d1117)',
    color: 'var(--text-primary, #e6edf3)',
    minHeight: '100vh',
  },
  header: {
    display: 'flex' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    marginBottom: '24px',
  },
  title: {
    fontSize: '24px',
    fontWeight: 700,
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '10px',
  },
  tabs: {
    display: 'flex' as const,
    gap: '0',
    borderBottom: '1px solid var(--border, #30363d)',
    marginBottom: '24px',
  },
  tab: (active: boolean) => ({
    padding: '10px 20px',
    cursor: 'pointer' as const,
    fontSize: '13px',
    fontWeight: 600,
    letterSpacing: '0.5px',
    color: active ? 'var(--blue, #58a6ff)' : 'var(--text-muted, #8b949e)',
    borderBottom: active ? '2px solid var(--blue, #58a6ff)' : '2px solid transparent',
    background: 'none',
    border: 'none',
    transition: 'color 0.2s',
  }),
  card: {
    backgroundColor: 'var(--bg-secondary, #161b22)',
    border: '1px solid var(--border, #30363d)',
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '12px',
  },
  grid: {
    display: 'grid' as const,
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '16px',
  },
  statusDot: (connected: boolean) => ({
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    backgroundColor: connected ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
    display: 'inline-block' as const,
  }),
  badge: (connected: boolean) => ({
    padding: '2px 8px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 600,
    backgroundColor: connected ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)',
    color: connected ? 'var(--green, #3fb950)' : 'var(--red, #f85149)',
  }),
  btn: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: '1px solid var(--border, #30363d)',
    backgroundColor: 'var(--bg-tertiary, #21262d)',
    color: 'var(--text-primary, #e6edf3)',
    cursor: 'pointer' as const,
    fontSize: '13px',
    display: 'flex' as const,
    alignItems: 'center' as const,
    gap: '6px',
  },
  btnPrimary: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: 'var(--blue, #58a6ff)',
    color: '#0d1117',
    cursor: 'pointer' as const,
    fontSize: '13px',
    fontWeight: 600,
  },
  btnDanger: {
    padding: '8px 16px',
    borderRadius: '6px',
    border: 'none',
    backgroundColor: 'var(--red, #f85149)',
    color: '#fff',
    cursor: 'pointer' as const,
    fontSize: '13px',
    fontWeight: 600,
  },
  progressBar: (pct: number) => ({
    height: '8px',
    borderRadius: '4px',
    backgroundColor: 'var(--bg-tertiary, #21262d)',
    overflow: 'hidden' as const,
    position: 'relative' as const,
    flex: 1,
  }),
  progressFill: (pct: number) => ({
    height: '100%',
    width: `${pct}%`,
    borderRadius: '4px',
    backgroundColor: pct === 100 ? 'var(--green, #3fb950)' : 'var(--blue, #58a6ff)',
    transition: 'width 0.3s',
  }),
  tableRow: {
    display: 'flex' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    padding: '10px 14px',
    borderBottom: '1px solid var(--border, #30363d)',
    cursor: 'pointer' as const,
    transition: 'background 0.15s',
  },
  logEntry: (level: string) => ({
    display: 'flex' as const,
    gap: '12px',
    padding: '8px 12px',
    fontSize: '13px',
    fontFamily: 'monospace',
    borderLeft: `3px solid ${level === 'ERROR' ? 'var(--red, #f85149)' : level === 'WARN' ? 'var(--amber, #e3b341)' : 'var(--blue, #58a6ff)'}`,
    marginBottom: '4px',
    backgroundColor: 'var(--bg-secondary, #161b22)',
    borderRadius: '0 4px 4px 0',
  }),
  levelBadge: (level: string) => ({
    fontSize: '11px',
    fontWeight: 700,
    padding: '1px 6px',
    borderRadius: '4px',
    minWidth: '44px',
    textAlign: 'center' as const,
    color: level === 'ERROR' ? 'var(--red, #f85149)' : level === 'WARN' ? 'var(--amber, #e3b341)' : 'var(--blue, #58a6ff)',
    backgroundColor: level === 'ERROR' ? 'rgba(248,81,73,0.12)' : level === 'WARN' ? 'rgba(227,179,65,0.12)' : 'rgba(88,166,255,0.12)',
  }),
  muted: {
    color: 'var(--text-muted, #8b949e)',
    fontSize: '13px',
  },
  filterBtn: (active: boolean) => ({
    padding: '4px 12px',
    borderRadius: '14px',
    border: active ? '1px solid var(--blue, #58a6ff)' : '1px solid var(--border, #30363d)',
    backgroundColor: active ? 'rgba(88,166,255,0.12)' : 'transparent',
    color: active ? 'var(--blue, #58a6ff)' : 'var(--text-muted, #8b949e)',
    cursor: 'pointer' as const,
    fontSize: '12px',
    fontWeight: 500,
  }),
}

type Tab = 'CONNECTION' | 'SEEDING' | 'TABLES' | 'LOGS'

// Build the connections list from live state where available so that the
// Bot Engine row never disagrees with the Header / Overview bot indicators.
function useConnections() {
  const bot = useBotStatus()
  const botUpdated = bot.last_heartbeat
    ? new Date(bot.last_heartbeat).toLocaleTimeString()
    : '—'
  return [
    { name: 'Alpaca SIP',   type: 'Market Data',  status: true,        latency: '12ms', lastChecked: '2 sec ago' },
    { name: 'Supabase',     type: 'Database',     status: true,        latency: '34ms', lastChecked: '5 sec ago' },
    { name: 'OPRA Options', type: 'Options Data', status: false,       latency: '--',   lastChecked: '1 min ago' },
    { name: 'Bot Engine',   type: 'Execution',    status: bot.online,  latency: '8ms',  lastChecked: botUpdated },
  ]
}

const seedingData = [
  { symbol: 'IWM', progress: 100 },
  { symbol: 'SPY', progress: 85 },
  { symbol: 'QQQ', progress: 72 },
  { symbol: 'AAPL', progress: 0 },
]

const tablesData = [
  { name: 'bars_1m', rows: 45230, columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol'] },
  { name: 'bars_15m', rows: 3015, columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol'] },
  { name: 'signals', rows: 1247, columns: ['id', 'timestamp', 'symbol', 'direction', 'strength', 'strategy_id'] },
  { name: 'portfolio_snapshots', rows: 890, columns: ['id', 'timestamp', 'equity', 'cash', 'positions_value'] },
  { name: 'strategies', rows: 5, columns: ['id', 'name', 'parameters', 'active', 'created_at'] },
]

const mockLogs = [
  { time: '2026-04-02 09:30:01', level: 'INFO', message: 'Market session opened. Starting data stream.' },
  { time: '2026-04-02 09:30:02', level: 'INFO', message: 'Alpaca SIP WebSocket connected successfully.' },
  { time: '2026-04-02 09:30:03', level: 'INFO', message: 'Subscribed to IWM, SPY, QQQ bar data.' },
  { time: '2026-04-02 09:30:15', level: 'WARN', message: 'OPRA options feed connection timeout. Retrying...' },
  { time: '2026-04-02 09:30:18', level: 'ERROR', message: 'OPRA connection failed after 3 attempts.' },
  { time: '2026-04-02 09:31:00', level: 'INFO', message: 'Inserted 60 bars into bars_1m table.' },
  { time: '2026-04-02 09:31:01', level: 'INFO', message: 'Signal generated: IWM BUY strength=0.82' },
  { time: '2026-04-02 09:32:00', level: 'INFO', message: 'Inserted 60 bars into bars_1m table.' },
  { time: '2026-04-02 09:33:00', level: 'INFO', message: 'Inserted 60 bars into bars_1m table.' },
  { time: '2026-04-02 09:33:05', level: 'WARN', message: 'Supabase response latency above threshold: 450ms' },
  { time: '2026-04-02 09:34:00', level: 'INFO', message: 'Inserted 60 bars into bars_1m table.' },
  { time: '2026-04-02 09:35:00', level: 'INFO', message: 'bars_15m aggregation complete for IWM, SPY, QQQ.' },
  { time: '2026-04-02 09:35:02', level: 'ERROR', message: 'Failed to write portfolio snapshot: constraint violation.' },
  { time: '2026-04-02 09:36:00', level: 'INFO', message: 'Inserted 60 bars into bars_1m table.' },
  { time: '2026-04-02 09:36:30', level: 'INFO', message: 'Daily P&L summary dispatched to Telegram.' },
]

export function DataView() {
  const [activeTab, setActiveTab] = useState<Tab>('CONNECTION')
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [logFilter, setLogFilter] = useState<string>('ALL')
  const connections = useConnections()

  const filteredLogs = logFilter === 'ALL' ? mockLogs : mockLogs.filter(l => l.level === logFilter)

  return (
    <div style={styles.container}>
      <PageHeader title="Data connections" subtitle="Feeds · Tables · Logs" />

      <div style={styles.tabs}>
        {(['CONNECTION', 'SEEDING', 'TABLES', 'LOGS'] as Tab[]).map(tab => (
          <button key={tab} style={styles.tab(activeTab === tab)} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'CONNECTION' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
            <button style={styles.btn}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>
          <div style={styles.grid}>
            {connections.map(conn => (
              <div key={conn.name} style={styles.card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {conn.type === 'Market Data' ? <Wifi size={16} /> : conn.type === 'Database' ? <Database size={16} /> : conn.type === 'Options Data' ? <Cloud size={16} /> : <Activity size={16} />}
                    <span style={{ fontWeight: 600, fontSize: '15px' }}>{conn.name}</span>
                  </div>
                  <span style={styles.badge(conn.status)}>
                    {conn.status ? 'CONNECTED' : 'DISCONNECTED'}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '6px' }}>
                  <div style={styles.muted}>Type: {conn.type}</div>
                  <div style={styles.muted}>Latency: <span style={{ color: 'var(--text-primary, #e6edf3)' }}>{conn.latency}</span></div>
                  <div style={styles.muted}>Last checked: {conn.lastChecked}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'SEEDING' && (
        <div>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
            <button style={styles.btnPrimary}>Start Seeding</button>
            <button style={styles.btnDanger}>Stop Seeding</button>
          </div>
          <div style={styles.card}>
            <div style={{ fontWeight: 600, marginBottom: '16px', fontSize: '15px' }}>Seeding Status</div>
            {seedingData.map(s => (
              <div key={s.symbol} style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '14px' }}>
                <span style={{ fontWeight: 600, minWidth: '50px', fontFamily: 'monospace' }}>{s.symbol}</span>
                <div style={styles.progressBar(s.progress)}>
                  <div style={styles.progressFill(s.progress)} />
                </div>
                <span style={{ minWidth: '44px', textAlign: 'right' as const, fontSize: '13px', fontWeight: 600, color: s.progress === 100 ? 'var(--green, #3fb950)' : s.progress === 0 ? 'var(--text-muted, #8b949e)' : 'var(--blue, #58a6ff)' }}>
                  {s.progress}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'TABLES' && (
        <div>
          <div style={styles.card}>
            <div style={{ fontWeight: 600, marginBottom: '12px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Table size={16} /> Supabase Tables
            </div>
            {tablesData.map(t => (
              <div key={t.name}>
                <div
                  style={{
                    ...styles.tableRow,
                    backgroundColor: selectedTable === t.name ? 'var(--bg-tertiary, #21262d)' : 'transparent',
                  }}
                  onClick={() => setSelectedTable(selectedTable === t.name ? null : t.name)}
                >
                  <span style={{ fontFamily: 'monospace', fontWeight: 500 }}>{t.name}</span>
                  <span style={styles.muted}>{t.rows.toLocaleString()} rows</span>
                </div>
                {selectedTable === t.name && (
                  <div style={{ padding: '12px 14px', backgroundColor: 'var(--bg-tertiary, #21262d)', borderBottom: '1px solid var(--border, #30363d)' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted, #8b949e)', marginBottom: '8px' }}>Schema Preview</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '6px' }}>
                      {t.columns.map(col => (
                        <span key={col} style={{ padding: '3px 10px', borderRadius: '4px', backgroundColor: 'var(--bg-secondary, #161b22)', border: '1px solid var(--border, #30363d)', fontSize: '12px', fontFamily: 'monospace' }}>
                          {col}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'LOGS' && (
        <div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
            <ScrollText size={16} style={{ color: 'var(--text-muted, #8b949e)' }} />
            <span style={{ ...styles.muted, marginRight: '8px' }}>Filter:</span>
            {['ALL', 'INFO', 'WARN', 'ERROR'].map(level => (
              <button key={level} style={styles.filterBtn(logFilter === level)} onClick={() => setLogFilter(level)}>
                {level}
              </button>
            ))}
          </div>
          <div style={{ maxHeight: '500px', overflowY: 'auto' as const }}>
            {filteredLogs.map((log, i) => (
              <div key={i} style={styles.logEntry(log.level)}>
                <span style={{ color: 'var(--text-muted, #8b949e)', minWidth: '155px', flexShrink: 0 }}>{log.time}</span>
                <span style={styles.levelBadge(log.level)}>{log.level}</span>
                <span>{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
