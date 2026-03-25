import React from 'react'
import { Play, Pause, Square, Plus, MoreVertical } from 'lucide-react'

export function StrategiesView() {
  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Agentic Strategies</h1>
        <button style={{ 
          display: 'flex', alignItems: 'center', padding: '10px 20px', 
          background: 'var(--blue)', color: 'white', border: 'none', 
          borderRadius: '4px', fontWeight: 600, cursor: 'pointer'
        }}>
          <Plus size={18} style={{ marginRight: '8px' }} />
          New Strategy
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
        <StrategyCard 
          name="UT Bot Scalper V2" 
          status="running" 
          symbol="IWM" 
          performance="+12.4%" 
          lastRun="2 mins ago" 
        />
        <StrategyCard 
          name="Trend Following EMA" 
          status="paused" 
          symbol="SPY" 
          performance="+5.2%" 
          lastRun="1 hour ago" 
        />
        <StrategyCard 
          name="Mean Reversion RSI" 
          status="stopped" 
          symbol="QQQ" 
          performance="-1.8%" 
          lastRun="Yesterday" 
        />
      </div>
    </div>
  )
}

function StrategyCard({ name, status, symbol, performance, lastRun }: any) {
  const isRunning = status === 'running'
  
  return (
    <div style={{ 
      background: 'var(--bg-secondary)', 
      borderRadius: '12px', 
      border: '1px solid var(--border)',
      padding: '20px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <div style={{ 
        position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', 
        background: isRunning ? 'var(--green)' : status === 'paused' ? 'var(--yellow)' : 'var(--text-muted)' 
      }} />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>{name}</h3>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Symbol: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{symbol}</span></div>
        </div>
        <MoreVertical size={18} color="var(--text-muted)" style={{ cursor: 'pointer' }} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Performance</div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: performance.startsWith('+') ? 'var(--green)' : 'var(--red)' }}>{performance}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>Last Run</div>
          <div style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{lastRun}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        {isRunning ? (
          <button style={actionBtnStyle}><Pause size={14} style={{ marginRight: '6px' }} /> Pause</button>
        ) : (
          <button style={{ ...actionBtnStyle, color: 'var(--green)' }}><Play size={14} style={{ marginRight: '6px' }} /> Start</button>
        )}
        <button style={actionBtnStyle}><Square size={14} style={{ marginRight: '6px' }} /> Stop</button>
      </div>
    </div>
  )
}

const actionBtnStyle = {
  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: '8px', background: 'var(--bg-primary)', border: '1px solid var(--border)',
  borderRadius: '4px', fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)',
  cursor: 'pointer'
}
