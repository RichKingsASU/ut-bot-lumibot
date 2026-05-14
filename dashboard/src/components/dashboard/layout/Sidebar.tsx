import React, { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  LineChart,
  Bitcoin,
  FlaskConical,
  Newspaper,
  Shield,
  Database,
  Bell,
  Settings,
  Server,
  Menu,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'

interface NavItem {
  label: string
  icon: React.ElementType
  path?: string
  parentPath?: string
  children?: { label: string; path: string }[]
}

const navItems: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard, path: '/' },
  {
    label: 'Equities',
    icon: LineChart,
    children: [
      { label: 'Trade', path: '/equities/trade' },
      { label: 'Monitor', path: '/equities/monitor' },
      { label: 'Performance', path: '/equities/performance' },
      { label: 'Strategy', path: '/equities/strategy' },
    ],
  },
  { label: '_separator_1', icon: LayoutDashboard, path: '_separator' },
  {
    label: 'Crypto',
    icon: Bitcoin,
    children: [
      { label: 'Trade', path: '/crypto/trade' },
      { label: 'Monitor', path: '/crypto/monitor' },
      { label: 'Performance', path: '/crypto/performance' },
      { label: 'Strategy', path: '/crypto/strategy' },
    ],
  },
  {
    label: 'Strategy Lab',
    icon: FlaskConical,
    parentPath: '/strategy-lab',
    children: [
      { label: 'Editor', path: '/strategy-lab/editor' },
      { label: 'Backtest & Replay', path: '/strategy-lab/backtest' },
    ],
  },
  // TODO: Re-enable News & Social nav when sentiment data sources are connected
  // {
  //   label: 'News & Social',
  //   icon: Newspaper,
  //   children: [
  //     { label: 'News Feed', path: '/news/feed' },
  //     { label: 'Sentiment', path: '/news/sentiment' },
  //     { label: 'Watchlist', path: '/news/watchlist' },
  //   ],
  // },
  {
    label: 'Risk Manager',
    icon: Shield,
    parentPath: '/risk-manager',
    children: [
      { label: 'Kill Switch', path: '/risk-manager' },
      { label: 'Position Sizing', path: '/risk/sizing' },
      { label: 'Risk Rules', path: '/risk/rules' },
      { label: 'Account Health', path: '/risk/health' },
    ],
  },
  { label: 'Data', icon: Database, path: '/data' },
  {
    label: 'Infrastructure',
    icon: Server,
    children: [
      { label: 'System Health', path: '/system-health' },
      { label: 'Alerts', path: '/alerts' },
    ],
  },
  { label: 'Settings', icon: Settings, path: '/settings' },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set())
  const location = useLocation()
  const navigate = useNavigate()

  // Auto-expand parent section when a child route is active
  useEffect(() => {
    for (const item of navItems) {
      if (item.children) {
        const isChildActive = item.children.some(
          (child) => location.pathname === child.path
        )
        if (isChildActive) {
          setExpandedSections((prev) => {
            const next = new Set(prev)
            next.add(item.label)
            return next
          })
        }
      }
    }
  }, [location.pathname])

  const toggleSection = (label: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(label)) {
        next.delete(label)
      } else {
        next.add(label)
      }
      return next
    })
  }

  const isActive = (path: string) => location.pathname === path

  const sidebarWidth = collapsed ? 60 : 200

  return (
    <nav
      style={{
        width: sidebarWidth,
        minWidth: sidebarWidth,
        height: '100%',
        background: '#161b22',
        borderRight: '1px solid #30363d',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease, min-width 0.2s ease',
        overflow: 'hidden',
      }}
    >
      {/* Toggle button */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-end',
          padding: '12px 8px',
          borderBottom: '1px solid #30363d',
        }}
      >
        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          style={{
            background: 'none',
            border: 'none',
            color: '#8b949e',
            cursor: 'pointer',
            padding: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 4,
          }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <Menu size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Nav items */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '8px 0' }}>
        {navItems.map((item) => {
          // Render separator — visible divider between Equities and Crypto
          if (item.path === '_separator') {
            return (
              <div
                key={item.label}
                aria-hidden="true"
                style={{
                  margin: '8px 12px',
                  height: 1,
                  background: 'linear-gradient(to right, rgba(255,255,255,0.18), rgba(255,255,255,0.04))',
                }}
              />
            )
          }

          const Icon = item.icon
          const hasChildren = !!item.children
          const isExpanded = expandedSections.has(item.label)
          const isParentActive =
            hasChildren &&
            item.children!.some((child) => location.pathname === child.path)
          const isSelfActive = item.path ? isActive(item.path) : false
          const highlighted = isSelfActive || isParentActive

          return (
            <div key={item.label}>
              {/* Parent / direct link */}
              {hasChildren ? (
                <button
                  onClick={() => {
                    if (item.parentPath) {
                      navigate(item.parentPath)
                      setExpandedSections((prev) => {
                        const next = new Set(prev)
                        next.add(item.label)
                        return next
                      })
                    } else {
                      toggleSection(item.label)
                    }
                  }}
                  aria-label={item.label}
                  aria-expanded={isExpanded}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: collapsed ? '10px 0' : '10px 12px',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    background: 'none',
                    border: 'none',
                    borderLeft: highlighted ? '3px solid #58a6ff' : '3px solid transparent',
                    color: highlighted ? '#58a6ff' : '#e6edf3',
                    cursor: 'pointer',
                    fontSize: 13,
                    textAlign: 'left',
                    whiteSpace: 'nowrap',
                  }}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon size={18} style={{ flexShrink: 0 }} />
                  {!collapsed && (
                    <>
                      <span style={{ flex: 1 }}>{item.label}</span>
                      {isExpanded ? (
                        <ChevronDown size={14} style={{ color: '#8b949e' }} />
                      ) : (
                        <ChevronRight size={14} style={{ color: '#8b949e' }} />
                      )}
                    </>
                  )}
                </button>
              ) : (
                <Link
                  to={item.path!}
                  aria-label={collapsed ? item.label : undefined}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: collapsed ? '10px 0' : '10px 12px',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    textDecoration: 'none',
                    borderLeft: isSelfActive ? '3px solid #58a6ff' : '3px solid transparent',
                    color: isSelfActive ? '#58a6ff' : '#e6edf3',
                    fontSize: 13,
                    whiteSpace: 'nowrap',
                  }}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon size={18} style={{ flexShrink: 0 }} />
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              )}

              {/* Children */}
              {hasChildren && isExpanded && !collapsed && (
                <div style={{ paddingLeft: 28 }}>
                  {item.children!.map((child) => {
                    const childActive = isActive(child.path)
                    return (
                      <Link
                        key={child.path}
                        to={child.path}
                        style={{
                          display: 'block',
                          padding: '7px 12px',
                          textDecoration: 'none',
                          fontSize: 12,
                          color: childActive ? '#58a6ff' : '#8b949e',
                          borderLeft: childActive
                            ? '2px solid #58a6ff'
                            : '2px solid transparent',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {child.label}
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer */}
      {!collapsed && (
        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid #30363d',
            color: '#8b949e',
            fontSize: 11,
            textAlign: 'center',
            whiteSpace: 'nowrap',
          }}
        >
          Disrupting Alpha v2.0
        </div>
      )}
    </nav>
  )
}
