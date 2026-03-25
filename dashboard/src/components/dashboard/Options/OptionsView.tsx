import React from 'react'
import { Layers } from 'lucide-react'

export function OptionsView() {
  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '24px' }}>Options Chain</h1>
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
        <Layers size={48} strokeWidth={1} style={{ marginBottom: '16px', opacity: 0.5 }} />
        <div>Options Analytics & Greeks (OPRA Feed Interface)</div>
      </div>
    </div>
  )
}
