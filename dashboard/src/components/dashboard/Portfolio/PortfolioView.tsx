import React from 'react';
import { motion } from 'framer-motion';
import { Wallet, TrendingUp, ArrowUpRight, ArrowDownRight, PieChart, Activity, Download, Globe } from 'lucide-react';
import { useTradingContext } from '../../../context/TradingContext';
import { PageHeader } from '../../ui/PageHeader';
import { MetricTile } from '../common/MetricTile';

export function PortfolioView() {
  const { account, positions, loading } = useTradingContext();
  const equity = account ? parseFloat(account.equity) : 0;
  const lastEquity = account ? parseFloat(account.last_equity) : equity;
  const dayPl = equity - lastEquity;
  const dayPlPct = lastEquity !== 0 ? (dayPl / lastEquity) * 100 : 0;
  const buyingPower = account ? parseFloat(account.buying_power) : 0;
  
  const formatCurrency = (val: number) => 
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  return (
    <div className="flex flex-col h-full bg-space overflow-hidden">
      {/* Header */}
      <div className="p-6 bg-surface-1/50 border-b border-border-muted backdrop-blur-md">
        <div className="flex items-center justify-between">
          <PageHeader 
            title="Capital Command" 
            subtitle="Real-time Portfolio Intelligence & Equity Surveillance" 
          />
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-surface-2 border border-border-muted rounded-lg text-xs font-bold text-secondary hover:text-vibrant transition-smooth">
                <Download className="w-3.5 h-3.5" />
                Export Ledger
            </button>
            <div className="px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-full text-[10px] font-bold text-blue-400">
                LIVE ACCOUNT
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <main className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          
          {/* Executive Metrics */}
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricTile 
                label="Total Equity" 
                value={loading ? '...' : formatCurrency(equity)} 
                change={`${dayPl >= 0 ? '+' : ''}${dayPlPct.toFixed(2)}%`} 
                isPositive={dayPl >= 0} 
                icon={Wallet}
                sparkline="M0,35 Q20,20 40,30 T80,10 T100,5"
            />
            <MetricTile 
                label="Day P&L" 
                value={loading ? '...' : formatCurrency(dayPl)} 
                change={`${dayPlPct.toFixed(2)}%`} 
                isPositive={dayPl >= 0} 
                icon={TrendingUp} 
                status={dayPl >= 0 ? 'fresh' : 'stale'}
            />
            <MetricTile 
                label="Buying Power" 
                value={loading ? '...' : formatCurrency(buyingPower)} 
                change="Real-time Max" 
                isPositive={true}
                icon={ArrowUpRight} 
            />
            <MetricTile 
                label="Open Exposure" 
                value={loading ? '...' : positions.length.toString()} 
                change={`${positions.length} Active Slots`} 
                isPositive={positions.length > 0} 
                icon={Activity} 
            />
          </section>

          {/* Equity Surveillance Chart */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Equity Curve Surveillance</h2>
                </div>
                <div className="flex gap-1 p-1 bg-surface-2/50 border border-border-muted rounded-lg">
                    {['1D', '1W', '1M', 'YTD', 'ALL'].map(t => (
                        <button key={t} className={`px-3 py-1 rounded-md text-[9px] font-bold transition-smooth ${t === '1D' ? 'bg-blue-600 text-white' : 'text-dim hover:text-secondary'}`}>{t}</button>
                    ))}
                </div>
            </div>
            
            <div className="h-[350px] glass-panel rounded-2xl border border-border-muted overflow-hidden relative group">
                <div className="absolute inset-0 bg-gradient-to-t from-emerald-500/5 to-transparent opacity-50" />
                {/* Mock High-Fidelity Chart */}
                <svg className="w-full h-full p-4" viewBox="0 0 1000 400" preserveAspectRatio="none">
                    <defs>
                        <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#10b981" stopOpacity="0.2" />
                            <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                        </linearGradient>
                    </defs>
                    <motion.path 
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: 2, ease: "easeInOut" }}
                        d="M0,350 L100,320 L200,340 L300,280 L400,300 L500,240 L600,260 L700,180 L800,200 L900,120 L1000,150" 
                        fill="none" 
                        stroke="#10b981" 
                        strokeWidth="3" 
                    />
                    <path d="M0,350 L100,320 L200,340 L300,280 L400,300 L500,240 L600,260 L700,180 L800,200 L900,120 L1000,150 V400 H0 Z" fill="url(#chartGradient)" />
                </svg>
                
                {/* Chart Overlays */}
                <div className="absolute top-8 left-8 space-y-1 pointer-events-none">
                    <div className="text-[10px] font-bold text-dim uppercase tracking-widest">ATH Baseline</div>
                    <div className="text-xl font-mono font-bold text-vibrant">$112,480.00</div>
                </div>
            </div>
          </section>

          {/* Allocation Heatmap Placeholder */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
             <div className="space-y-4">
                <div className="flex items-center gap-2">
                    <PieChart className="w-4 h-4 text-purple-400" />
                    <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Asset Allocation Heatmap</h2>
                </div>
                <div className="h-64 bg-surface-1 border border-border-muted rounded-2xl p-6 flex items-center justify-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5" />
                    <div className="text-center space-y-2 relative z-10">
                        <PieChart className="w-12 h-12 text-dim mx-auto opacity-20" />
                        <p className="text-[11px] text-dim font-bold uppercase tracking-widest">Allocation Matrix Loading</p>
                    </div>
                </div>
             </div>

             <div className="space-y-4">
                <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-blue-400" />
                    <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Global Exposure Risk</h2>
                </div>
                <div className="h-64 bg-surface-1 border border-border-muted rounded-2xl p-6 space-y-4">
                    {[
                        { label: 'Technology', pct: '42%', color: 'bg-blue-500' },
                        { label: 'Finance', pct: '18%', color: 'bg-emerald-500' },
                        { label: 'Energy', pct: '12%', color: 'bg-amber-500' },
                        { label: 'Unallocated', pct: '28%', color: 'bg-surface-2' }
                    ].map((item, i) => (
                        <div key={i} className="space-y-1.5">
                            <div className="flex justify-between text-[10px] font-bold">
                                <span className="text-secondary">{item.label}</span>
                                <span className="text-vibrant">{item.pct}</span>
                            </div>
                            <div className="h-1.5 bg-surface-0 rounded-full overflow-hidden">
                                <motion.div className={`h-full ${item.color}`} initial={{ width: 0 }} animate={{ width: item.pct }} />
                            </div>
                        </div>
                    ))}
                </div>
             </div>
          </section>
        </main>

        {/* Executive Sidebar */}
        <aside className="w-80 border-l border-border-muted bg-surface-1/30 p-6 space-y-8 hidden xl:block">
            <div className="space-y-4">
                <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Session P&L Summary</h2>
                <div className="p-5 glass-panel rounded-2xl border border-border-muted space-y-6">
                    <div>
                        <div className="text-[9px] font-bold text-dim uppercase tracking-widest mb-1">Realized Gains</div>
                        <div className="text-lg font-mono font-bold text-emerald-400">+$1,240.42</div>
                    </div>
                    <div>
                        <div className="text-[9px] font-bold text-dim uppercase tracking-widest mb-1">Unrealized P&L</div>
                        <div className="text-lg font-mono font-bold text-rose-400">-$420.18</div>
                    </div>
                    <div className="pt-4 border-t border-border-muted">
                        <div className="text-[9px] font-bold text-dim uppercase tracking-widest mb-1">Net Expected</div>
                        <div className="text-2xl font-mono font-bold text-gradient-blue">+$820.24</div>
                    </div>
                </div>
            </div>

            <div className="p-6 bg-gradient-to-br from-blue-600/10 to-purple-600/10 border border-blue-500/20 rounded-2xl text-center space-y-2">
                <Activity className="w-8 h-8 text-blue-400 mx-auto mb-2 opacity-50" />
                <h3 className="text-[11px] font-bold text-vibrant uppercase tracking-widest">Performance Engine</h3>
                <p className="text-[10px] text-dim leading-relaxed">Portfolio volatility is currently 1.2σ below historical baseline.</p>
            </div>
        </aside>
      </div>
    </div>
  );
}
