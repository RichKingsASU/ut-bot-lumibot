import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  LineChart,
  Bitcoin,
  FlaskConical,
  Shield,
  Database,
  Settings,
  Server,
  Menu,
  ChevronLeft,
  ChevronDown,
  Terminal,
  Activity,
  Zap,
  Lock,
  PieChart
} from 'lucide-react';

interface NavItem {
  label: string;
  icon: React.ElementType;
  path?: string;
  section?: 'operations' | 'research' | 'safety' | 'infra';
  children?: { label: string; path: string }[];
}

const navItems: NavItem[] = [
  { label: 'Control Tower', icon: LayoutDashboard, path: '/', section: 'operations' },
  {
    label: 'Equities Monitor',
    icon: LineChart,
    section: 'operations',
    children: [
      { label: 'Surveillance', path: '/equities/monitor' },
      { label: 'Execution', path: '/equities/trade' },
    ],
  },
  {
    label: 'Crypto Command',
    icon: Bitcoin,
    section: 'operations',
    children: [
      { label: 'Surveillance', path: '/crypto/monitor' },
      { label: 'Execution', path: '/crypto/trade' },
    ],
  },
  {
    label: 'Strategy Lab',
    icon: FlaskConical,
    section: 'research',
    children: [
      { label: 'Intelligence', path: '/strategy-lab' },
      { label: 'Simulator', path: '/strategy-lab/backtest' },
    ],
  },
  {
    label: 'Risk Center',
    icon: Shield,
    section: 'safety',
    children: [
      { label: 'Intervention', path: '/risk-manager' },
      { label: 'Capital Health', path: '/risk/health' },
    ],
  },
  {
    label: 'System',
    icon: Server,
    section: 'infra',
    children: [
      { label: 'Core Health', path: '/system-health' },
      { label: 'Settings', path: '/settings' },
    ],
  },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    navItems.forEach(item => {
      if (item.children?.some(c => location.pathname === c.path)) {
        setExpandedSections(prev => new Set(prev).add(item.label));
      }
    });
  }, [location.pathname]);

  const toggleSection = (label: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      next.has(label) ? next.delete(label) : next.add(label);
      return next;
    });
  };

  return (
    <nav 
      className={`h-full flex flex-col bg-surface-1 border-r border-border-muted transition-all duration-300 ease-in-out shadow-2xl z-50 ${collapsed ? 'w-20' : 'w-64'}`}
    >
      {/* Brand Header */}
      <div className="p-6 border-b border-border-muted/50 flex items-center justify-between overflow-hidden">
        <div className="flex items-center gap-3 overflow-hidden">
          <img src="/logo.png" alt="DA" className="w-8 h-8 object-contain flex-shrink-0" />
          <AnimatePresence mode="wait">
            {!collapsed && (
              <motion.div 
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="flex flex-col"
              >
                <h1 className="text-sm font-bold text-vibrant tracking-tighter leading-none">DISRUPTING</h1>
                <p className="text-[10px] font-bold text-blue-400 tracking-[0.2em] leading-tight">ALPHA</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <button 
          onClick={() => setCollapsed(!collapsed)}
          className="p-2 hover:bg-surface-2 rounded-xl transition-smooth text-dim hover:text-vibrant"
        >
          {collapsed ? <Menu className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-8 custom-scrollbar">
        {['operations', 'research', 'safety', 'infra'].map(sectionKey => {
            const items = navItems.filter(i => i.section === sectionKey);
            if (items.length === 0) return null;

            return (
                <div key={sectionKey} className="space-y-1">
                    {!collapsed && (
                        <h2 className="px-4 text-[9px] font-bold text-dim uppercase tracking-[0.2em] mb-3">{sectionKey}</h2>
                    )}
                    {items.map(item => {
                        const Icon = item.icon;
                        const isExpanded = expandedSections.has(item.label);
                        const isChildActive = item.children?.some(c => location.pathname === c.path);
                        const isSelfActive = item.path === location.pathname;
                        const isActive = isSelfActive || isChildActive;

                        return (
                            <div key={item.label} className="space-y-1">
                                {item.children ? (
                                    <button 
                                        onClick={() => toggleSection(item.label)}
                                        className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-smooth group ${isActive ? 'bg-blue-500/10 text-blue-400' : 'text-secondary hover:bg-surface-2 hover:text-vibrant'}`}
                                    >
                                        <Icon className={`w-4 h-4 ${isActive ? 'text-blue-400' : 'text-dim group-hover:text-vibrant'}`} />
                                        {!collapsed && (
                                            <>
                                                <span className="flex-1 text-left text-xs font-semibold">{item.label}</span>
                                                <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} />
                                            </>
                                        )}
                                    </button>
                                ) : (
                                    <Link 
                                        to={item.path!}
                                        className={`flex items-center gap-3 px-4 py-2.5 rounded-xl transition-smooth group ${isActive ? 'bg-blue-500/10 text-blue-400 shadow-[inset_0_0_12px_rgba(59,130,246,0.1)]' : 'text-secondary hover:bg-surface-2 hover:text-vibrant'}`}
                                    >
                                        <Icon className={`w-4 h-4 ${isActive ? 'text-blue-400' : 'text-dim group-hover:text-vibrant'}`} />
                                        {!collapsed && <span className="text-xs font-semibold">{item.label}</span>}
                                    </Link>
                                )}

                                <AnimatePresence>
                                    {isExpanded && !collapsed && item.children && (
                                        <motion.div 
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: 'auto' }}
                                            exit={{ opacity: 0, height: 0 }}
                                            className="overflow-hidden pl-11 space-y-1"
                                        >
                                            {item.children.map(child => (
                                                <Link 
                                                    key={child.path}
                                                    to={child.path}
                                                    className={`block py-1.5 text-[11px] font-medium transition-smooth ${location.pathname === child.path ? 'text-blue-400' : 'text-dim hover:text-secondary'}`}
                                                >
                                                    {child.label}
                                                </Link>
                                            ))}
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        );
                    })}
                </div>
            );
        })}
      </div>

      {/* Footer / Status */}
      <div className="p-6 border-t border-border-muted/50">
        {!collapsed ? (
            <div className="flex flex-col gap-4">
                <div className="p-3 bg-surface-2 rounded-xl border border-border-muted space-y-2">
                    <div className="flex justify-between items-center text-[9px] font-bold">
                        <span className="text-dim uppercase tracking-wider">Engine Load</span>
                        <span className="text-emerald-400">14%</span>
                    </div>
                    <div className="h-1 bg-surface-0 rounded-full overflow-hidden">
                        <div className="w-[14%] h-full bg-emerald-500" />
                    </div>
                </div>
                <div className="flex items-center justify-between px-1">
                    <div className="flex items-center gap-2">
                        <Activity className="w-3.5 h-3.5 text-emerald-500 animate-pulse" />
                        <span className="text-[10px] font-bold text-secondary uppercase tracking-widest">Live Feed</span>
                    </div>
                    <div className="flex items-center gap-1.5 p-1 bg-zinc-800 rounded text-dim">
                        <Lock className="w-3 h-3" />
                    </div>
                </div>
            </div>
        ) : (
            <div className="flex flex-col items-center gap-4">
                <Activity className="w-5 h-5 text-emerald-500 animate-pulse" />
            </div>
        )}
      </div>
    </nav>
  );
}
