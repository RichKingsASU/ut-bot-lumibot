import React, { useState, useEffect, useCallback } from 'react'
import { Bell, ToggleLeft, ToggleRight, Filter, CheckCircle2, AlertCircle, RefreshCw, Cpu, Activity } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'

interface AlertItem {
  id: string | number
  timestamp: Date
  timeRaw: string
  symbol?: string
  action?: string
  confidence?: number
  asset_class?: string
  message: string
  category: string
  verdict?: string
  delivered: boolean
}

export function AlertsView() {
  const [alertsEnabled, setAlertsEnabled] = useState(true)
  const [filterType, setFilterType] = useState('ALL') // ALL | CRYPTO | EQUITIES | BUY | SELL
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true)
      
      // 1. Fetch Agent Signals
      const { data: signalsData } = await supabase
        .from('agent_signals')
        .select('id, symbol, action, confidence, asset_class, created_at, reasoning')
        .order('created_at', { ascending: false })
        .limit(50)

      // 2. Fetch System/Watchdog Alerts (if table exists)
      let systemAlerts: any[] = []
      try {
        const { data } = await supabase
          .from('system_alerts')
          .select('id, ts, category, message, level, is_resolved')
          .order('ts', { ascending: false })
          .limit(20)
        systemAlerts = data || []
      } catch (e) {
        console.warn('system_alerts table query skipped or failed:', e)
      }

      // 3. Map & Merge into a single feed
      const mappedSignals: AlertItem[] = (signalsData || []).map(s => {
        let verdict = ''
        if (s.reasoning) {
          try {
            const parsed = typeof s.reasoning === 'string' ? JSON.parse(s.reasoning) : s.reasoning
            verdict = parsed.verdict || parsed.reasoning || ''
          } catch {
            verdict = String(s.reasoning)
          }
        }
        const actionStr = (s.action || 'HOLD').toUpperCase()
        const assetClassStr = (s.asset_class || 'EQUITY').toUpperCase()
        return {
          id: `sig-${s.id}`,
          timestamp: new Date(s.created_at),
          timeRaw: s.created_at,
          symbol: s.symbol,
          action: actionStr,
          confidence: s.confidence != null ? parseFloat(s.confidence) : 0.5,
          asset_class: assetClassStr === 'EQUITIES' ? 'EQUITY' : assetClassStr,
          message: `${actionStr} ${s.symbol} | Confidence: ${Math.round((s.confidence || 0.5) * 100)}%`,
          category: 'SIGNAL',
          verdict: verdict,
          delivered: true
        }
      })

      const mappedSystem: AlertItem[] = systemAlerts.map(a => ({
        id: `sys-${a.id}`,
        timestamp: new Date(a.ts),
        timeRaw: a.ts,
        message: a.message,
        category: (a.category || 'SYSTEM').toUpperCase(),
        delivered: true
      }))

      const combined = [...mappedSignals, ...mappedSystem].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
      
      setAlerts(combined)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('Error fetching alerts:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 20000)
    return () => clearInterval(interval)
  }, [fetchAlerts])

  const getRelativeTime = (date: Date) => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000)
    if (seconds < 60) return 'just now'
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    return `${days}d ago`
  }

  // Filter client-side
  const filteredAlerts = alerts.filter(alert => {
    if (filterType === 'ALL') return true
    if (filterType === 'CRYPTO') return alert.asset_class === 'CRYPTO'
    if (filterType === 'EQUITIES') return alert.asset_class === 'EQUITY'
    if (filterType === 'BUY') return alert.action === 'BUY'
    if (filterType === 'SELL') return alert.action === 'SELL'
    return true
  })

  return (
    <div style={containerStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <PageHeader title="Surveillance Alerts" subtitle="Unified intelligence & anomaly logs" />
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button 
            onClick={fetchAlerts} 
            disabled={loading}
            style={{ padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Sync Feed
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div style={filterBarStyle}>
        {['ALL', 'CRYPTO', 'EQUITIES', 'BUY', 'SELL'].map(type => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            style={{
              padding: '6px 16px',
              borderRadius: '20px',
              border: 'none',
              background: filterType === type ? 'var(--blue)' : 'var(--bg-tertiary)',
              color: filterType === type ? '#0d1117' : 'var(--text-primary)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Feed Container */}
      <div style={feedContainerStyle}>
        {loading && alerts.length === 0 ? (
          <div style={emptyStateStyle}>
            <RefreshCw size={24} className="animate-spin" style={{ marginBottom: '12px', color: 'var(--blue)' }} />
            Loading live alert matrix...
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div style={emptyStateStyle}>
            <Bell size={24} style={{ marginBottom: '12px', color: 'var(--text-muted)' }} />
            No active alerts matching the current filter.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredAlerts.map((alert) => {
              const isSignal = alert.category === 'SIGNAL'
              const isBuy = alert.action === 'BUY'
              const isSell = alert.action === 'SELL'
              const color = isSignal ? (isBuy ? 'var(--green)' : isSell ? 'var(--red)' : 'var(--text-muted)') : 'var(--blue)'

              return (
                <div key={alert.id} style={{ ...alertCardStyle, borderLeft: `4px solid ${color}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 700,
                        backgroundColor: isSignal ? 'rgba(88,166,255,0.1)' : 'rgba(245,158,11,0.1)',
                        color: isSignal ? 'var(--blue)' : '#f59e0b'
                      }}>
                        {alert.category}
                      </span>
                      {alert.symbol && <span style={{ fontWeight: 700, fontSize: '14px' }}>{alert.symbol}</span>}
                      {alert.action && (
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontSize: '10px',
                          fontWeight: 700,
                          backgroundColor: isBuy ? 'rgba(63,185,80,0.15)' : isSell ? 'rgba(248,81,73,0.15)' : 'rgba(139,148,158,0.15)',
                          color: color
                        }}>
                          {alert.action}
                        </span>
                      )}
                      {alert.asset_class && (
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          • {alert.asset_class}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                      {getRelativeTime(alert.timestamp)}
                    </span>
                  </div>

                  <div style={{ marginTop: '8px', fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.5 }}>
                    {alert.message}
                  </div>

                  {alert.verdict && (
                    <div style={{ marginTop: '10px', padding: '10px', background: 'var(--bg-tertiary)', borderRadius: '6px', fontSize: '12px', color: 'var(--text-muted)', borderLeft: '2px solid var(--border)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                        <Cpu size={12} /> Decision Reasoning Verdict
                      </div>
                      {alert.verdict}
                    </div>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px', borderTop: '1px solid rgba(48,54,61,0.3)', paddingTop: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--green)' }}>
                      <CheckCircle2 size={12} /> Delivered
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

const containerStyle = { padding: '24px', flex: 1, overflow: 'auto', backgroundColor: 'var(--bg-primary, #0d1117)', color: 'var(--text-primary)' }
const filterBarStyle = { display: 'flex', gap: '8px', marginBottom: '24px' }
const feedContainerStyle = { background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '12px', padding: '20px' }
const alertCardStyle = { padding: '16px', background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: '8px' }
const emptyStateStyle = { padding: '48px 0', textAlign: 'center' as const, color: 'var(--text-muted)', display: 'flex', flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center' }
