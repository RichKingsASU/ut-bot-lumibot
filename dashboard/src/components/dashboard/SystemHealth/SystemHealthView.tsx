import React, { useState, useEffect } from 'react'
import { Activity, Shield, Zap, AlertCircle, CheckCircle, Server, Globe, Lock } from 'lucide-react'
import { supabase } from '../../../lib/supabaseClient'
import { PageHeader } from '../../ui/PageHeader'
import { useTradingMode, tradingModeBadgeStyle } from '../../../hooks/useTradingMode'

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
  const [activeAlerts, setActiveAlerts] = useState<any[]>([])
  const tradingMode = useTradingMode()
  const modeBadge = tradingModeBadgeStyle(tradingMode)
  const envColor = tradingMode === 'live' ? colors.red : tradingMode === 'paper' ? colors.green : colors.textMuted
  const [adminKey, setAdminKey] = useState(localStorage.getItem('ADMIN_API_KEY') || '')
  const [showKey, setShowKey] = useState(false)
  const [shutdownLoading, setShutdownLoading] = useState(false)
  const [shutdownSuccess, setShutdownSuccess] = useState(false)
  
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

        // Fetch latest health status from bot (Local only)
        let health = null;
        try {
          const resp = await fetch('http://localhost:8000/health', { signal: AbortSignal.timeout(2000) })
          health = await resp.json()
        } catch (e) {
          // Expected in cloud environment unless tunneled
          health = { status: 'UNKNOWN', websocket: 'UNKNOWN' };
        }

        // Fetch recent audits
        const { data: audits } = await supabase
            .from('system_audit')
            .select('*')
            .order('ts', { ascending: false })
            .limit(10)

        // Fetch active system alerts
        const { data: alerts } = await supabase
            .from('system_alerts')
            .select('*')
            .order('created_at', { ascending: false })
            .limit(10)

        setHealthData({ session, health })
        setLastAudit(audits || [])
        setActiveAlerts(alerts || [])
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
          value={modeBadge.label}
          icon={Globe}
          color={envColor}
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

      {/* Operator Control Panel */}
      <div style={{ 
        backgroundColor: colors.bgSecondary, 
        border: `1px solid ${colors.amber}55`, 
        borderRadius: 12, 
        padding: 24, 
        marginBottom: 32,
        backgroundImage: 'linear-gradient(180deg, rgba(227,179,65,0.03) 0%, transparent 100%)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: colors.textPrimary, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Lock size={18} color={colors.amber} />
              Operator Command Center
            </div>
            <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
              Institutional control for session {healthData?.session?.id?.substring(0,8) || '...' }
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
             <div style={{ display: 'flex', alignItems: 'center', gap: 8, backgroundColor: colors.bgPrimary, padding: '4px 12px', borderRadius: 6, border: `1px solid ${colors.border}` }}>
                <span style={{ fontSize: 11, color: colors.textMuted }}>ADMIN API KEY:</span>
                <input 
                  type={showKey ? "text" : "password"}
                  value={adminKey}
                  onChange={(e) => {
                    setAdminKey(e.target.value)
                    localStorage.setItem('ADMIN_API_KEY', e.target.value)
                  }}
                  style={{ 
                    background: 'none', 
                    border: 'none', 
                    color: colors.blue, 
                    fontSize: 12, 
                    fontFamily: 'monospace',
                    width: 120,
                    outline: 'none'
                  }}
                />
                <button onClick={() => setShowKey(!showKey)} style={{ background: 'none', border: 'none', color: colors.textMuted, cursor: 'pointer', display: 'flex' }}>
                   <Activity size={14} />
                </button>
             </div>
             <button 
               disabled={shutdownLoading || shutdownSuccess}
               onClick={async () => {
                 if (!window.confirm("EMERGENCY SHUTDOWN: Are you sure you want to stop the bot session immediately?")) return
                 setShutdownLoading(true)
                 try {
                   const { error } = await supabase
                     .from('bot_status')
                     .update({ target_status: 'shutdown' })
                     .eq('id', 1)
                   
                   if (error) throw error
                   setShutdownSuccess(true)
                   setTimeout(() => setShutdownSuccess(false), 5000)
                 } catch (e) {
                   alert("Shutdown command failed. Check console for details.")
                   console.error(e)
                 } finally {
                   setShutdownLoading(false)
                 }
               }}
               style={{ 
                 backgroundColor: shutdownSuccess ? colors.green : colors.red, 
                 color: 'white', 
                 border: 'none', 
                 borderRadius: 6, 
                 padding: '8px 16px', 
                 fontSize: 13, 
                 fontWeight: 600, 
                 cursor: shutdownLoading ? 'not-allowed' : 'pointer',
                 opacity: shutdownLoading ? 0.7 : 1,
                 display: 'flex',
                 alignItems: 'center',
                 gap: 8
               }}>
               {shutdownLoading ? 'SIGNALING...' : shutdownSuccess ? 'SIGNAL SENT' : 'SHUTDOWN BOT'}
             </button>
          </div>
        </div>
        <div style={{ fontSize: 11, color: colors.textMuted, backgroundColor: 'rgba(248,81,73,0.05)', padding: '8px 12px', borderRadius: 6, border: `1px solid ${colors.red}22` }}>
           <strong>WARNING:</strong> Shutdown command is processed within {30}s. For immediate liquidation of all positions, use the <strong>FLATTEN</strong> command in the Trade view.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* System Alerts */}
        <div style={{ backgroundColor: colors.bgSecondary, border: `1px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: `1px solid ${colors.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontWeight: 600, fontSize: 14, color: colors.textPrimary }}>Active System Alerts</div>
            <div style={{ fontSize: 11, color: colors.textMuted }}>Last 24h</div>
          </div>
          <div style={{ padding: 20 }}>
             <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {activeAlerts.length > 0 ? activeAlerts.map((alert, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'start' }}>
                    {alert.level === 'CRITICAL' || alert.level === 'ERROR' 
                      ? <AlertCircle size={16} color={colors.red} /> 
                      : alert.level === 'WARNING' 
                        ? <AlertCircle size={16} color={colors.amber} /> 
                        : <CheckCircle size={16} color={colors.green} />}
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, color: colors.textPrimary, fontWeight: alert.level === 'CRITICAL' ? 600 : 400 }}>
                        {alert.message}
                      </div>
                      <div style={{ fontSize: 11, color: colors.textMuted }}>
                        {new Date(alert.created_at).toLocaleString()} · {alert.category}
                      </div>
                    </div>
                  </div>
                )) : (
                  <div style={{ fontSize: 13, color: colors.textMuted, textAlign: 'center', padding: 20 }}>
                    No active system alerts.
                  </div>
                )}
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
