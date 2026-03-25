import React from 'react'
import { History } from 'lucide-react'

export function BacktestView() {
  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '24px' }}>Strategy Backtesting</h1>
      <div style={{ 
        height: 'calc(100vh - 200px)', 
        background: 'var(--bg-secondary)', 
        borderRadius: '8px', 
        border: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted)'
      }}>
        <History size={48} strokeWidth={1} style={{ marginBottom: '16px', opacity: 0.5 }} />
        <div>Lumibot Backtest Results & Logs</div>
      </div>
    </div>
  )
}
