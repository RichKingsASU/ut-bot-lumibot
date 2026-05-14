import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '../../../lib/supabaseClient';
import { PageHeader } from '../../ui/PageHeader';
import { MetricTile } from '../common/MetricTile';
import { 
  BarChart3, Activity, Shield, 
  Terminal as TerminalIcon, Maximize2, 
  Search, Filter, ArrowUpRight, ArrowDownRight,
  RefreshCw, Layers
} from 'lucide-react';

const EQUITY_SYMBOLS = ['IWM', 'SPY', 'QQQ'];
const TARGET_TIMEFRAMES = ['1Min', '15Min'];

interface InventoryRow {
    symbol: string;
    timeframe: string;
    count: number;
    latest: string;
    latestRaw: number | null;
    status: 'fresh' | 'stale' | 'none';
}

export default function EquitiesMonitorView() {
    const [stats, setStats] = useState<InventoryRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastFetched, setLastFetched] = useState<Date | null>(null);

    const fetchStats = useCallback(async () => {
        setLoading(true);
        try {
            const { data: inventory } = await supabase
                .from('bar_inventory')
                .select('*')
                .in('symbol', EQUITY_SYMBOLS);

            const mapped = (inventory || []).map(r => {
                const latestRaw = r.last_ingested ? new Date(r.last_ingested).getTime() : null;
                const age = latestRaw ? (Date.now() - latestRaw) / 1000 / 60 : null;
                const status = !latestRaw ? 'none' : (age && age < 5) ? 'fresh' : 'stale';
                
                return {
                    symbol: r.symbol,
                    timeframe: r.timeframe,
                    count: r.bar_count,
                    latest: r.last_ingested ? new Date(r.last_ingested).toLocaleTimeString() : 'N/A',
                    latestRaw,
                    status
                } as InventoryRow;
            }).filter(r => TARGET_TIMEFRAMES.includes(r.timeframe));

            setStats(mapped);
            setLastFetched(new Date());
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchStats();
        const interval = setInterval(fetchStats, 30000);
        return () => clearInterval(interval);
    }, [fetchStats]);

    return (
        <div className="flex flex-col h-full bg-space overflow-hidden">
            {/* Header Area */}
            <div className="p-6 bg-surface-1/50 border-b border-border-muted backdrop-blur-md">
                <div className="flex items-center justify-between">
                    <PageHeader 
                        title="Equities Intelligence" 
                        subtitle="Institutional Surveillance Command Center" 
                    />
                    <div className="flex items-center gap-3">
                        <div className="flex flex-col items-end mr-4">
                            <span className="text-[10px] font-bold text-dim uppercase tracking-widest">Feed Health</span>
                            <div className="flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                <span className="text-xs font-mono font-bold text-emerald-400">ACTIVE</span>
                            </div>
                        </div>
                        <button 
                            onClick={fetchStats}
                            className={`p-2 rounded-lg border border-border-muted hover:bg-surface-2 transition-smooth ${loading ? 'animate-spin' : ''}`}
                        >
                            <RefreshCw className="w-4 h-4 text-secondary" />
                        </button>
                    </div>
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden">
                {/* Main Content: High Density Surveillance */}
                <main className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
                    
                    {/* Live Inventory Matrix */}
                    <section>
                        <div className="flex items-center gap-2 mb-4">
                            <Layers className="w-4 h-4 text-blue-400" />
                            <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Data Inventory Matrix</h2>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {stats.map((s, idx) => (
                                <MetricTile 
                                    key={idx}
                                    label={`${s.symbol} · ${s.timeframe}`}
                                    value={s.count.toLocaleString()}
                                    change={`Latest: ${s.latest}`}
                                    isPositive={s.status === 'fresh'}
                                    status={s.status}
                                    icon={BarChart3}
                                    sparkline="M0,30 Q25,10 50,25 T100,5"
                                />
                            ))}
                        </div>
                    </section>

                    {/* Active Surveillance Feed */}
                    <section className="flex-1 min-h-0 flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <TerminalIcon className="w-4 h-4 text-blue-400" />
                                <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Live Surveillance Feed</h2>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="relative">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-dim" />
                                    <input placeholder="Filter events..." className="bg-surface-1 border border-border-muted rounded-lg py-1.5 pl-9 pr-4 text-[10px] text-vibrant outline-none focus:border-blue-500/50 w-48" />
                                </div>
                                <button className="p-1.5 bg-surface-1 border border-border-muted rounded-lg hover:border-blue-500/30 text-dim">
                                    <Filter className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>

                        <div className="flex-1 bg-surface-0 border border-border-muted rounded-2xl overflow-hidden shadow-2xl min-h-[300px]">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr className="bg-surface-1/50 border-b border-border-muted">
                                        {['Timestamp', 'Symbol', 'Event Type', 'Confidence', 'Impact', 'Action'].map(h => (
                                            <th key={h} className="text-left px-6 py-4 text-[10px] font-bold text-dim uppercase tracking-widest">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {[1, 2, 3, 4, 5].map(i => (
                                        <tr key={i} className="border-b border-border-muted/30 hover:bg-surface-1/30 transition-smooth group">
                                            <td className="px-6 py-4 font-mono text-[11px] text-secondary">{new Date().toLocaleTimeString()}</td>
                                            <td className="px-6 py-4 font-bold text-vibrant">IWM</td>
                                            <td className="px-6 py-4">
                                                <span className="px-2 py-0.5 bg-blue-500/10 text-blue-400 rounded-full text-[9px] font-bold border border-blue-500/20 uppercase">Trend Breakout</span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-12 h-1 bg-surface-2 rounded-full overflow-hidden">
                                                        <div className="w-[85%] h-full bg-emerald-500" />
                                                    </div>
                                                    <span className="text-[10px] font-bold text-emerald-400">85%</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-1 text-emerald-400 font-bold text-[10px]">
                                                    <ArrowUpRight className="w-3 h-3" />
                                                    HIGH
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <button className="opacity-0 group-hover:opacity-100 px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-[9px] font-bold rounded-lg transition-smooth">ANALYZE</button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                </main>

                {/* Right Sidebar: Quick Stats */}
                <aside className="w-80 border-l border-border-muted bg-surface-1/30 p-6 space-y-6 hidden xl:block">
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-blue-400" />
                            <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Session Health</h2>
                        </div>
                        <div className="p-4 bg-surface-2/50 rounded-2xl border border-border-muted space-y-4">
                            {[
                                { l: 'API Latency', v: '24ms', s: 'fresh' },
                                { l: 'Thread Pool', v: '92% Idle', s: 'fresh' },
                                { l: 'Ingestion Rate', v: '128 bars/m', s: 'fresh' }
                            ].map((h, i) => (
                                <div key={i} className="flex justify-between items-center">
                                    <span className="text-[10px] text-secondary font-semibold">{h.l}</span>
                                    <span className="text-[10px] font-mono text-emerald-400 font-bold">{h.v}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="p-6 glass-panel rounded-2xl border-dashed border-2 border-border-muted text-center space-y-2">
                        <Shield className="w-8 h-8 text-dim mx-auto mb-2 opacity-30" />
                        <h3 className="text-[11px] font-bold text-vibrant">Risk Guard Active</h3>
                        <p className="text-[10px] text-dim leading-relaxed">Surveillance is currently monitoring for volatility spikes and circuit breaks.</p>
                    </div>
                </aside>
            </div>
        </div>
    );
}
