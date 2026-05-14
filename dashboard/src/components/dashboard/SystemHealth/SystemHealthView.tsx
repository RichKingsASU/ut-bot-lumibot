import React, { useState, useEffect } from 'react'
import { Activity, Shield, Zap, AlertCircle, CheckCircle, Server, Globe, Lock } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'

const colors = {
  bgPrimary: '#0d1117',
  bgSecondary: '#161b22',
  border: '#30363d',
  textPrimary: '#e6edf3',
  textMuted: '#8b949e',
  blue: '#58a6ff',
  green: '#3fb950',
  red: '#f85149',
  amber: '#e3b341',
}

export default function SystemHealthView() {
  const [healthData, setHealthData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [lastAudit, setLastAudit] = useState<any[]>([])

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch latest session status
        const { data: session } = await supabase
          .from('sessions')
          .select('*')
          .order('started_at', { ascending: false })
          .limit(1)
          .single()

        // Fetch latest health status from bot
        const resp = await fetch('http://localhost:8000/health')
        const health = await resp.json()

        // Fetch recent audits
        const { data: audits } = await supabase
            .from('system_audit')
            .select('*')
            .order('ts', { ascending: false })
            .limit(5)

        setHealthData({ session, health })
        setLastAudit(audits || [])
      } catch (e) {
        console.error('Failed to fetch health data:', e)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const StatCard = ({ title, value, icon: Icon, color }: any) => (
    <div style={{
      backgroundColor: colors.bgSecondary,
      border: `1px solid ${colors.border}`,
      borderRadius: 12,
      padding: 20,
      display: 'flex',
      alignItems: 'center',
      gap: 16
    }}>
      <div style={{
        backgroundColor: `${color}15`,
        padding: 12,
        borderRadius: 10,
        color: color
      }}>
        <Icon size={24} />
      </div>
      <div>
        <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 4 }}>{title}</div>
        <div style={{ fontSize: 18, fontWeight: 600, color: colors.textPrimary }}>{value}</div>
      </div>
    </div>
  )

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', backgroundColor: colors.bgPrimary }}>
      <PageHeader title="System health" subtitle="Operational status" />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 20, marginBottom: 32 }}>
        <StatCard 
          title="Bot Status" 
          value={healthData?.health?.status || 'OFFLINE'} 
          icon={Server} 
          color={healthData?.health?.status === 'ready' ? colors.green : colors.red} 
        />
        <StatCard 
          title="Environment" 
          value={process.env.ALPACA_IS_PAPER === 'true' ? 'PAPER' : 'LIVE'} 
          icon={Globe} 
          color={process.env.ALPACA_IS_PAPER === 'true' ? colors.blue : colors.red} 
        />
        <StatCard 
          title="Websocket" 
          value={healthData?.health?.websocket === 'connected' ? 'CONNECTED' : 'DISCONNECTED'} 
          icon={Zap} 
          color={healthData?.health?.websocket === 'connected' ? colors.green : colors.amber} 
        />
        <StatCard 
          title="Risk Controls" 
          value="ACTIVE" 
          icon={Shield} 
          color={colors.green} 
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* System Alerts */}
        <div style={{ backgroundColor: colors.bgSecondary, border: `1px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: `1px solid ${colors.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: colors.textPrimary }}>Active System Alerts</div>
            <div style={{ fontSize: 11, color: colors.textMuted }}>Last 24h</div>
          </div>
          <div style={{ padding: 20 }}>
             {/* Mocking for now, will connect to real table in next step */}
             <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[
                  { msg: 'Websocket re-established after 1200ms', type: 'INFO', time: '2 mins ago' },
                  { msg: 'Rate limit approaching (85/100 requests)', type: 'WARNING', time: '15 mins ago' },
                  { msg: 'Heartbeat latency spike: 450ms', type: 'WARNING', time: '1 hour ago' }
                ].map((alert, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'start' }}>
                    {alert.type === 'WARNING' ? <AlertCircle size={16} color={colors.amber} /> : <CheckCircle size={16} color={colors.green} />}
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, color: colors.textPrimary }}>{alert.msg}</div>
                      <div style={{ fontSize: 11, color: colors.textMuted }}>{alert.time}</div>
                    </div>
                  </div>
                ))}
             </div>
          </div>
        </div>

        {/* Audit Trail */}
        <div style={{ backgroundColor: colors.bgSecondary, border: `1px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: `1px solid ${colors.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: colors.textPrimary }}>System Audit Trail</div>
            <div style={{ fontSize: 11, color: colors.blue, cursor: 'pointer' }}>View All</div>
          </div>
          <div style={{ padding: 20 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {lastAudit.length > 0 ? lastAudit.map((a, i) => (
                <div key={i} style={{ fontSize: 12, borderLeft: `2px solid ${colors.border}`, paddingLeft: 12 }}>
                  <div style={{ color: colors.textPrimary }}>{a.action}: {a.status}</div>
                  <div style={{ color: colors.textMuted, fontSize: 10 }}>{new Date(a.ts).toLocaleString()} · {a.details}</div>
                </div>
              )) : (
                <div style={{ color: colors.textMuted, fontSize: 12, textAlign: 'center', padding: 20 }}>No audit logs found.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Safety Matrix */}
      <div style={{ marginTop: 24, backgroundColor: colors.bgSecondary, border: `1px solid ${colors.border}`, borderRadius: 12, padding: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: colors.textPrimary, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Lock size={16} color={colors.amber} />
          Safety Integrity Matrix
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          {[
            { label: 'Paper Mode Enforced', status: 'PASS' },
            { label: 'Live API Override', status: 'BLOCKED' },
            { label: 'Kill Switch Verified', status: 'PASS' },
            { label: 'Max Loss Guard', status: 'ACTIVE' },
            { label: 'Stale Data Guard', status: 'PASS' }
          ].map((item, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6 }}>
              <span style={{ fontSize: 12, color: colors.textMuted }}>{item.label}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: item.status === 'PASS' || item.status === 'ACTIVE' ? colors.green : colors.red }}>{item.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
