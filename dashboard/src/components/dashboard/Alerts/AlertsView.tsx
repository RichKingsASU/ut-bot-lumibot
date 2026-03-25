import React from 'react'
import { Bell, Filter } from 'lucide-react'

export function AlertsView() {
  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Signal Alerts</h1>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button style={{ 
            display: 'flex', alignItems: 'center', padding: '8px 12px', 
            background: 'var(--bg-secondary)', border: '1px solid var(--border)', 
            borderRadius: '4px', color: 'var(--text-primary)', cursor: 'pointer'
          }}>
            <Filter size={16} style={{ marginRight: '8px' }} />
            Filter
          </button>
          <button style={{ 
            padding: '8px 12px', background: 'var(--red)', border: 'none', 
            borderRadius: '4px', color: 'white', fontWeight: 600, cursor: 'pointer'
          }}>
            Clear All
          </button>
        </div>
      </div>

      <div style={{ 
        background: 'var(--bg-secondary)', 
        borderRadius: '8px', 
        border: '1px solid var(--border)',
        overflow: 'hidden'
      }}>
        <AlertItem 
          time="2026-03-25 10:45:02" 
          symbol="IWM" 
          type="BUY" 
          message="UT Bot Signal: Strong Buy @ 201.45" 
          priority="high" 
        />
        <AlertItem 
          time="2026-03-25 10:30:15" 
          symbol="SPY" 
          type="TRAIL" 
          message="Trailing Stop Adjusted: 512.20" 
          priority="medium" 
        />
        <AlertItem 
          time="2026-03-25 09:15:00" 
          symbol="QQQ" 
          type="SELL" 
          message="Trend Reversal: Exit All Longs" 
          priority="high" 
        />
      </div>
    </div>
  )
}

function AlertItem({ time, symbol, type, message, priority }: any) {
  const color = type === 'BUY' ? 'var(--green)' : type === 'SELL' ? 'var(--red)' : 'var(--blue)'
  
  return (
    <div style={{ 
      padding: '166px', 
      borderBottom: '1px solid var(--border)', 
      display: 'flex', 
      alignItems: 'center',
      gap: '20px'
    }}>
      <div style={{ color: 'var(--text-muted)', fontSize: '12px', width: '140px' }}>{time}</div>
      <div style={{ 
        padding: '4px 8px', borderRadius: '4px', background: color + '22', 
        color: color, fontWeight: 700, fontSize: '12px', minWidth: '60px', textAlign: 'center' 
      }}>{type}</div>
      <div style={{ fontWeight: 600, color: 'var(--text-primary)', width: '60px' }}>{symbol}</div>
      <div style={{ flex: 1, color: 'var(--text-muted)', fontSize: '14px' }}>{message}</div>
      <Bell size={16} color={priority === 'high' ? 'var(--red)' : 'var(--text-muted)'} />
    </div>
  )
}
