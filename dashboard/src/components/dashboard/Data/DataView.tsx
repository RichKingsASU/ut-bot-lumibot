import React from 'react'
import { Database, Cloud, AlertCircle } from 'lucide-react'
import SeedStatus from '../../SeedStatus'

export function DataView() {
  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Data Inventory</h1>
        <div style={{ display: 'flex', gap: '12px' }}>
          <StatusBadge icon={Cloud} label="Alpaca SIP" status="connected" />
          <StatusBadge icon={Database} label="Supabase" status="connected" />
        </div>
      </div>

      <div style={{ marginBottom: '32px' }}>
        <SeedStatus />
      </div>

      <div style={{ 
        background: 'var(--bg-secondary)', 
        padding: '20px', 
        borderRadius: '8px', 
        border: '1px solid var(--border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px', color: 'var(--blue)' }}>
          <AlertCircle size={18} style={{ marginRight: '8px' }} />
          <span style={{ fontWeight: 600 }}>Active Feeds</span>
        </div>
        <div style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
          SIP Real-time Equity (IWM, SPY, QQQ) - Active<br />
          OPRA Options Chain (Weekly) - Ready<br />
          Historical Backfill - 98% Complete
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ icon: Icon, label, status }: any) {
  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      padding: '6px 12px', 
      background: 'var(--bg-secondary)', 
      borderRadius: '20px',
      border: '1px solid var(--border)',
      fontSize: '12px',
      fontWeight: 600
    }}>
      <Icon size={14} style={{ marginRight: '6px' }} />
      <span style={{ color: 'var(--text-muted)', marginRight: '6px' }}>{label}:</span>
      <span style={{ color: status === 'connected' ? 'var(--green)' : 'var(--red)' }}>
        {status.toUpperCase()}
      </span>
    </div>
  )
}
