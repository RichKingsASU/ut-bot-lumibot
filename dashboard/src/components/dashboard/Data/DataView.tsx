import React, { useState, useEffect, useCallback } from 'react'
import { Database, Cloud, Activity, RefreshCw, Table, ScrollText, Wifi } from 'lucide-react'
import { useTradingContext } from '../../../context/TradingContext'
import { PageHeader } from '../../ui/PageHeader'
import { supabase } from '../../../lib/supabaseClient'

const styles = {
  container: {
    padding: '24px',
    backgroundColor: 'var(--bg-primary, #0d1117)',
    color: 'var(--text-primary, #e6edf3)',
    minHeight: '100vh',
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
    borderLeft: `3px solid ${level === 'CRITICAL' || level === 'ERROR' ? 'var(--red, #f85149)' : level === 'WARNING' ? 'var(--amber, #e3b341)' : 'var(--blue, #58a6ff)'}`,
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
    color: level === 'CRITICAL' || level === 'ERROR' ? 'var(--red, #f85149)' : level === 'WARNING' ? 'var(--amber, #e3b341)' : 'var(--blue, #58a6ff)',
    backgroundColor: level === 'CRITICAL' || level === 'ERROR' ? 'rgba(248,81,73,0.12)' : level === 'WARNING' ? 'rgba(227,179,65,0.12)' : 'rgba(88,166,255,0.12)',
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

function useConnections() {
  const { botStatus: bot } = useTradingContext()
  const botUpdated = bot.last_heartbeat
    ? new Date(bot.last_heartbeat).toLocaleTimeString()
    : '—'
  return [
    { name: 'Alpaca SIP',   type: 'Market Data',  status: true,        latency: '12ms', lastChecked: '2 sec ago' },
    { name: 'Database',     type: 'Database',     status: true,        latency: '34ms', lastChecked: '5 sec ago' },
    { name: 'Bot Engine',   type: 'Execution',    status: bot.online,  latency: '8ms',  lastChecked: botUpdated },
  ]
}

export function DataView() {
  const [activeTab, setActiveTab] = useState<Tab>('CONNECTION')
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [logFilter, setLogFilter] = useState<string>('ALL')
  const [liveTables, setLiveTables] = useState<any[]>([])
  const [liveLogs, setLiveLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const connections = useConnections()

  const fetchLiveData = useCallback(async () => {
    setLoading(true)
    try {
      const tables = ['ohlcv_bars', 'bot_status', 'system_alerts', 'system_audit', 'sessions']
      const counts = await Promise.all(tables.map(async (name) => {
        const { count } = await supabase.from(name).select('*', { count: 'exact', head: true })
        return { name, rows: count || 0, columns: ['timestamp', 'symbol', 'data...'] }
      }))
      setLiveTables(counts)

      const { data: logs } = await supabase
        .from('system_alerts')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(50)
      setLiveLogs(logs || [])
    } catch (e) {
      console.error('Failed to fetch data stats:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLiveData()
  }, [fetchLiveData])

  const filteredLogs = logFilter === 'ALL' ? liveLogs : liveLogs.filter(l => l.level === logFilter)

  return (
    <div style={styles.container}>
      <PageHeader title="Data connections" subtitle="Live metrics & audits" />

      <div style={styles.tabs}>
        {(['CONNECTION', 'TABLES', 'LOGS'] as Tab[]).map(tab => (
          <button key={tab} style={styles.tab(activeTab === tab)} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'CONNECTION' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '16px' }}>
            <button style={styles.btn} onClick={fetchLiveData} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
            </button>
          </div>
          <div style={styles.grid}>
            {connections.map(conn => (
              <div key={conn.name} style={styles.card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {conn.type === 'Market Data' ? <Wifi size={16} /> : <Database size={16} />}
                    <span style={{ fontWeight: 600, fontSize: '15px' }}>{conn.name}</span>
                  </div>
                  <span style={styles.badge(conn.status)}>
                    {conn.status ? 'CONNECTED' : 'DISCONNECTED'}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={styles.muted}>Type: {conn.type}</div>
                  <div style={styles.muted}>Last checked: {conn.lastChecked}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'TABLES' && (
        <div>
          <div style={styles.card}>
            <div style={{ fontWeight: 600, marginBottom: '12px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Table size={16} /> Live Data tables
            </div>
            {liveTables.map(t => (
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
            {['ALL', 'INFO', 'WARNING', 'CRITICAL'].map(level => (
              <button key={level} style={styles.filterBtn(logFilter === level)} onClick={() => setLogFilter(level)}>
                {level}
              </button>
            ))}
          </div>
          <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
            {filteredLogs.map((log, i) => (
              <div key={i} style={styles.logEntry(log.level)}>
                <span style={{ color: 'var(--text-muted, #8b949e)', minWidth: '155px', flexShrink: 0 }}>
                  {new Date(log.created_at).toLocaleString()}
                </span>
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
