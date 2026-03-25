import React from 'react'
import { Wallet, TrendingUp, ArrowUpRight, ArrowDownRight } from 'lucide-react'

export function PortfolioView() {
  return (
    <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>Portfolio Overview</h1>
        <div style={{ 
          padding: '8px 16px', 
          background: 'var(--blue)', 
          borderRadius: '4px', 
          color: 'white', 
          fontWeight: 600,
          cursor: 'pointer'
        }}>
          Export Data
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        <StatCard title="Total Equity" value="$124,500.20" change="+2.4%" positive={true} icon={Wallet} />
        <StatCard title="Day P&L" value="$1,240.50" change="+1.02%" positive={true} icon={TrendingUp} />
        <StatCard title="Buying Power" value="$48,200.00" change="Stable" positive={null} icon={ArrowUpRight} />
        <StatCard title="Open Positions" value="8" change="-2" positive={false} icon={ArrowDownRight} />
      </div>

      <div style={{ 
        height: '400px', 
        background: 'var(--bg-secondary)', 
        borderRadius: '8px', 
        border: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-muted)',
        fontSize: '14px'
      }}>
        Equity Curve Chart Loading (Supabase `portfolio_snapshots`)
      </div>
    </div>
  )
}

function StatCard({ title, value, change, positive, icon: Icon }: any) {
  return (
    <div style={{ 
      padding: '20px', 
      background: 'var(--bg-secondary)', 
      borderRadius: '8px', 
      border: '1px solid var(--border)',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</span>
        <Icon size={18} color="var(--blue)" />
      </div>
      <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>{value}</div>
      <div style={{ 
        fontSize: '13px', 
        fontWeight: 600, 
        color: positive === true ? 'var(--green)' : positive === false ? 'var(--red)' : 'var(--text-muted)' 
      }}>
        {change} {positive !== null && (positive ? '↑' : '↓')}
      </div>
    </div>
  )
}
