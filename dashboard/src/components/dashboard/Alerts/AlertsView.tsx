import React, { useState } from 'react'
import { Bell, Filter } from 'lucide-react'
import { useTradingContext } from '../../../context/TradingContext'

export function AlertsView() {
  const { signals, symbol } = useTradingContext()
  const [filterType, setFilterType] = useState<'ALL' | 'BUY' | 'SELL'>('ALL')
  
  const reverseSignals = [...signals].reverse()
  const filteredSignals = reverseSignals.filter(sig => filterType === 'ALL' || sig.type === filterType)
  
  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Signal Alerts ({filteredSignals.length})</h1>
        <div style={{ display: 'flex', gap: '12px' }}>
          <select 
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as any)}
            style={{ 
              padding: '8px 32px 8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', 
              borderRadius: '4px', color: 'var(--text-primary)', cursor: 'pointer', appearance: 'none',
              backgroundImage: 'url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23bdc1c6%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E")',
              backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px top 50%', backgroundSize: '12px auto'
            }}
          >
            <option value="ALL">All Types</option>
            <option value="BUY">Buy Only</option>
            <option value="SELL">Sell Only</option>
          </select>
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
        {filteredSignals.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No '{filterType}' signals generated for {symbol} yet.
          </div>
        ) : (
          filteredSignals.map((sig, idx) => (
            <AlertItem 
              key={`${sig.time}-${idx}`}
              time={new Date(sig.time * 1000).toLocaleString()} 
              symbol={symbol} 
              type={sig.type} 
              message={`UT Bot Signal: ${sig.type === 'BUY' ? 'Strong Buy' : 'Strong Sell'} @ ${sig.price.toFixed(2)}`} 
              priority="high" 
            />
          ))
        )}
      </div>
    </div>
  )
}

function AlertItem({ time, symbol, type, message, priority }: any) {
  const color = type === 'BUY' ? 'var(--green)' : type === 'SELL' ? 'var(--red)' : 'var(--blue)'
  
  return (
    <div style={{ 
      padding: '16px', 
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
