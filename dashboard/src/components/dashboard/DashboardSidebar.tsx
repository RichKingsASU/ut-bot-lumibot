import React from 'react'
import {
  LineChart,
  Layers,
  Bitcoin,
  History,
  Wallet,
  Database,
  Bell,
  Settings,
  Menu,
  ChevronLeft
} from 'lucide-react'

export type DashboardScreen =
  | 'portfolio'
  | 'trade'
  | 'options'
  | 'crypto'
  | 'backtest'
  | 'data'
  | 'alerts'
  | 'settings'

interface DashboardSidebarProps {
  activeScreen: DashboardScreen
  onScreenChange: (screen: DashboardScreen) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

const NAV_ITEMS: { key: DashboardScreen; label: string; icon: React.ElementType }[] = [
  { key: 'portfolio', label: 'Portfolio', icon: Wallet },
  { key: 'trade', label: 'Trade', icon: LineChart },
  { key: 'options', label: 'Options', icon: Layers },
  { key: 'crypto', label: 'Crypto', icon: Bitcoin },
  { key: 'backtest', label: 'Backtest', icon: History },
  { key: 'data', label: 'Data', icon: Database },
  { key: 'alerts', label: 'Alerts', icon: Bell },
  { key: 'settings', label: 'Settings', icon: Settings },
]

export function DashboardSidebar({ 
  activeScreen, 
  onScreenChange, 
  collapsed = false, 
  onToggleCollapse 
}: DashboardSidebarProps) {
  return (
    <div style={{
      width: collapsed ? '60px' : '200px',
      flexShrink: 0,
      background: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      transition: 'width 0.2s ease-in-out',
      overflow: 'hidden'
    }}>
      {/* Toggle Button */}
      <div style={{
        padding: '12px',
        display: 'flex',
        justifyContent: collapsed ? 'center' : 'flex-end',
        borderBottom: '1px solid var(--border)',
        cursor: 'pointer',
        color: 'var(--text-muted)'
      }} onClick={onToggleCollapse}>
        {collapsed ? <Menu size={20} /> : <ChevronLeft size={20} />}
      </div>

      {/* Nav List */}
      <div style={{ flex: 1, padding: '12px 0' }}>
        {NAV_ITEMS.map((item) => {
          const isActive = activeScreen === item.key
          const Icon = item.icon
          
          return (
            <div
              key={item.key}
              onClick={() => onScreenChange(item.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: collapsed ? '12px 0' : '10px 16px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                cursor: 'pointer',
                background: isActive ? 'var(--bg-tertiary)' : 'transparent',
                color: isActive ? 'var(--blue)' : 'var(--text-muted)',
                borderLeft: isActive ? '3px solid var(--blue)' : '3px solid transparent',
                marginBottom: '4px',
                transition: 'all 0.15s ease'
              }}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={20} style={{ minWidth: '20px' }} />
              {!collapsed && (
                <span style={{ 
                  marginLeft: '12px', 
                  fontSize: '14px', 
                  fontWeight: isActive ? 600 : 500,
                  whiteSpace: 'nowrap'
                }}>
                  {item.label}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer / Info */}
      {!collapsed && (
        <div style={{ 
          padding: '16px', 
          borderTop: '1px solid var(--border)', 
          fontSize: '11px', 
          color: 'var(--text-muted)',
          textAlign: 'center'
        }}>
          Disrupting Alpha v1.0
        </div>
      )}
    </div>
  )
}
