import React, { useState, useEffect } from 'react'
import { fmtPrice, fmtTime } from '../../utils/formatters'
import { DataInventory } from '../DataInventory'
import type { BotStatusData } from '../../hooks/useBotStatus'

interface BotStatusProps {
  symbol: string
  timeframe: string
  atrPeriod: number
  sensitivity: number
  currentATR: number
  currentTrailStop: number
  lastSignal: string
  iterationsToday: number
  connected: boolean
  botStatus: BotStatusData
}

function getMarketStatus(): 'OPEN' | 'CLOSED' | 'PRE' | 'AFTER' {
  const now = new Date()
  const est = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const h = est.getHours()
  const m = est.getMinutes()
  const mins = h * 60 + m
  const day = est.getDay()

  if (day === 0 || day === 6) return 'CLOSED'
  if (mins < 4 * 60) return 'CLOSED'
  if (mins < 9 * 60 + 30) return 'PRE'
  if (mins < 16 * 60) return 'OPEN'
  if (mins < 20 * 60) return 'AFTER'
  return 'CLOSED'
}

function getMarketCloseCountdown(): string {
  const now = new Date()
  const est = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const closeMs = new Date(est)
  closeMs.setHours(16, 0, 0, 0)
  const diff = closeMs.getTime() - est.getTime()
  if (diff <= 0) return 'Market Closed'
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  return `${h}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`
}

const statusColors: Record<string, string> = {
  OPEN: 'var(--green)', CLOSED: 'var(--red)', PRE: 'var(--amber)', AFTER: 'var(--amber)'
}

export const BotStatus: React.FC<BotStatusProps> = ({
  symbol, timeframe, atrPeriod, sensitivity,
  currentATR, currentTrailStop, lastSignal, iterationsToday, connected, botStatus,
}: BotStatusProps) => {
  const [now, setNow] = useState(new Date())
  const [activeTab, setActiveTab] = useState<'status' | 'inventory'>('status')

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const marketStatus = getMarketStatus()
  const countdown = getMarketCloseCountdown()
  const estTime = fmtTime(now)

  const row = (label: string, val: React.ReactNode, color?: string) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{label}</span>
      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, fontWeight: 500, color: color ?? 'var(--text-primary)' }}>{val}</span>
    </div>
  )

  const TabButton = ({ id, label }: { id: 'status' | 'inventory', label: string }) => (
    <button 
      onClick={() => setActiveTab(id)}
      style={{
        padding: '6px 12px',
        fontSize: 10,
        fontWeight: 700,
        background: activeTab === id ? 'var(--bg-card)' : 'transparent',
        borderBottom: activeTab === id ? '2px solid var(--brand)' : 'none',
        color: activeTab === id ? 'var(--text-primary)' : 'var(--text-muted)',
        cursor: 'pointer',
        transition: 'all 0.2s'
      }}
    >
      {label}
    </button>
  )

  return (
    <div style={{ padding: '0px' }}>
      <div style={{ display: 'flex', background: 'var(--bg-header)', borderBottom: '1px solid var(--border)' }}>
        <TabButton id="status" label="BOT STATUS" />
        <TabButton id="inventory" label="DATA INVENTORY" />
      </div>

      <div style={{ padding: '12px' }}>
        {activeTab === 'status' ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 18, fontFamily: 'JetBrains Mono, monospace', color: 'var(--text-primary)' }}>{estTime} EST</span>
            </div>

            {row('Symbol', symbol)}
            {row('Timeframe', timeframe)}
            {row('ATR Period', atrPeriod)}
            {row('Sensitivity', sensitivity.toFixed(1))}
            {row('Current ATR', `$${fmtPrice(currentATR, 4)}`)}
            {row('Trail Stop', `$${fmtPrice(currentTrailStop)}`)}
            {row('Last Signal', lastSignal || '—', lastSignal === 'BUY' ? 'var(--green)' : lastSignal === 'SELL' ? 'var(--red)' : 'var(--text-muted)')}
            {row('Iterations Today', String(iterationsToday))}

            <div style={{ marginTop: 8, padding: '8px 0', borderTop: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>MARKET STATUS</span>
                <span className="badge" style={{
                  background: `${statusColors[marketStatus]}22`,
                  color: statusColors[marketStatus],
                  border: `1px solid ${statusColors[marketStatus]}55`,
                  fontSize: 11,
                }}>{marketStatus}</span>
              </div>
              {marketStatus === 'OPEN' && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>MARKET CLOSE IN</div>
                  <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: 'var(--amber)' }}>{countdown}</div>
                </div>
              )}
            </div>

            <div style={{ marginTop: 4 }}>
              {row('Data Feed', connected ? '● LIVE' : '● OFFLINE', connected ? 'var(--green)' : 'var(--red)')}
              {row('Bot Status',
                botStatus.online ? '● LIVE' : botStatus.status === 'stale' ? '● STALE' : botStatus.status === 'connecting' ? '● CONNECTING' : '● OFFLINE',
                botStatus.online ? 'var(--green)' : botStatus.status === 'stale' || botStatus.status === 'connecting' ? 'var(--amber)' : 'var(--red)'
              )}
              {botStatus.online && botStatus.mode && row('Mode', botStatus.mode.toUpperCase())}
              {botStatus.online && botStatus.uptime_seconds != null && row('Uptime', `${Math.floor(botStatus.uptime_seconds / 3600)}h ${Math.floor((botStatus.uptime_seconds % 3600) / 60).toString().padStart(2, '0')}m`)}
              {botStatus.online && botStatus.last_signal && row('Last Signal', botStatus.last_signal, botStatus.last_signal === 'CALL' ? 'var(--green)' : botStatus.last_signal === 'PUT' ? 'var(--red)' : 'var(--text-muted)')}
            </div>
          </div>
        ) : (
          <DataInventory />
        )}
      </div>
    </div>
  )
}

