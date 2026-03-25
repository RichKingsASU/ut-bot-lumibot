import React, { useState } from 'react'
import { Database, Cloud, AlertCircle, Activity, RefreshCw } from 'lucide-react'
import SeedStatus from '../../SeedStatus'
import { useTradingContext } from '../../../context/TradingContext'

export function DataInventoryView() {
  const { connected: alpacaConnected } = useTradingContext()
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = () => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1000)
  }

  const dataFeeds = [
    { id: 1, name: 'Alpaca SIP Real-time Equity', type: 'WebSocket', status: alpacaConnected ? 'ACTIVE' : 'DISCONNECTED', latency: alpacaConnected ? '12ms' : '-', updated: 'Just now' },
    { id: 2, name: 'OPRA Options Chain', type: 'REST API', status: 'READY', latency: '45ms', updated: '2 mins ago' },
    { id: 3, name: 'Historical Bar Backfill', type: 'Database (Supabase)', status: 'SYNCING', latency: '-', updated: '98% Complete' },
    { id: 4, name: 'Crypto News Sentiment', type: 'Webhook', status: 'ACTIVE', latency: '120ms', updated: '15 mins ago' },
    { id: 5, name: 'Federal Reserve Info', type: 'Batch', status: 'IDLE', latency: '-', updated: 'Yesterday' },
  ]

  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Data Inventory</h1>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button 
            onClick={handleRefresh}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: 'transparent', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text-primary)', cursor: 'pointer' }}
          >
            <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
            Refresh
          </button>
          <StatusBadge icon={Cloud} label="Alpaca SIP" status={alpacaConnected ? 'connected' : 'disconnected'} />
          <StatusBadge icon={Database} label="Supabase" status="connected" />
        </div>
      </div>

      <div style={{ marginBottom: '32px' }}>
        <SeedStatus />
      </div>

      <div style={{ 
        background: 'var(--bg-secondary)', 
        borderRadius: '8px', 
        border: '1px solid var(--border)',
        overflow: 'hidden'
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', color: 'var(--blue)' }}>
          <Activity size={18} style={{ marginRight: '8px' }} />
          <span style={{ fontWeight: 600 }}>Active Feeds & Integrations</span>
        </div>
        
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
              <th style={{ padding: '12px 20px', fontWeight: 600 }}>SOURCE NAME</th>
              <th style={{ padding: '12px 20px', fontWeight: 600 }}>TYPE</th>
              <th style={{ padding: '12px 20px', fontWeight: 600 }}>STATUS</th>
              <th style={{ padding: '12px 20px', fontWeight: 600 }}>LATENCY</th>
              <th style={{ padding: '12px 20px', fontWeight: 600 }}>LAST UPDATED</th>
            </tr>
          </thead>
          <tbody>
            {dataFeeds.map((feed) => (
              <tr key={feed.id} style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-primary)' }}>
                <td style={{ padding: '16px 20px', fontWeight: 600 }}>{feed.name}</td>
                <td style={{ padding: '16px 20px', color: 'var(--text-muted)' }}>{feed.type}</td>
                <td style={{ padding: '16px 20px' }}>
                  <span style={{ 
                    padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
                    background: feed.status === 'ACTIVE' || feed.status === 'READY' ? 'rgba(46,160,67,0.1)' : feed.status === 'SYNCING' ? 'rgba(88,166,255,0.1)' : 'rgba(240,113,120,0.1)',
                    color: feed.status === 'ACTIVE' || feed.status === 'READY' ? 'var(--green)' : feed.status === 'SYNCING' ? 'var(--blue)' : 'var(--red)'
                  }}>
                    {feed.status}
                  </span>
                </td>
                <td style={{ padding: '16px 20px', color: 'var(--text-muted)' }}>{feed.latency}</td>
                <td style={{ padding: '16px 20px', color: 'var(--text-muted)' }}>{feed.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
