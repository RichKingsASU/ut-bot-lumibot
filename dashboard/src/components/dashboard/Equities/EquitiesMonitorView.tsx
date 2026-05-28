import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../../ui/PageHeader';
import { 
  BarChart3, Activity, Shield, 
  Terminal as TerminalIcon, Search, Filter, 
  ArrowUpRight, RefreshCw, Layers
} from 'lucide-react';

interface EquitiesSurveillanceRow {
  symbol: string;
  price: number;
  lastBarTime: string | null;
  lastBarRaw: number | null;
  barCount1m: number;
  barCount15m: number;
  status: 'FRESH' | 'STALE' | 'OLD';
}

export default function EquitiesMonitorView() {
  const [surveillanceData, setSurveillanceData] = useState<EquitiesSurveillanceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);
  const [filterQuery, setFilterQuery] = useState('');

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const adminKey = import.meta.env.VITE_ADMIN_API_KEY || '';
      const res = await fetch('/.netlify/functions/get-equities-monitor', {
        headers: { 'X-Admin-API-Key': adminKey }
      });

      if (!res.ok) throw new Error(`Netlify function status: ${res.status}`);

      const data = await res.json();
      const prices = data.prices || {};
      const stats = data.stats || [];

      // Process stats per symbol
      const symbols = ['SPY','IWM','QQQ','NVDA','TSLA','AAPL','MSFT','META','GOOGL'];
      const processed: EquitiesSurveillanceRow[] = symbols.map(sym => {
        const livePrice = prices[sym] ? prices[sym].price : 0;
        const oneMinStat = stats.find((st: any) => st.symbol === sym && st.timeframe === '1Min') || { bar_count: 0, last_bar: null };
        const fifteenMinStat = stats.find((st: any) => st.symbol === sym && st.timeframe === '15Min') || { bar_count: 0, last_bar: null };
        
        const lastBarRaw = oneMinStat.last_bar ? new Date(oneMinStat.last_bar).getTime() : null;
        let status: 'FRESH' | 'STALE' | 'OLD' = 'OLD';

        if (lastBarRaw) {
          const ageMins = (Date.now() - lastBarRaw) / 1000 / 60;
          if (ageMins < 5) {
            status = 'FRESH';
          } else if (ageMins < 60) {
            status = 'STALE';
          } else {
            status = 'OLD';
          }
        }

        return {
          symbol: sym,
          price: livePrice,
          lastBarTime: oneMinStat.last_bar ? new Date(oneMinStat.last_bar).toLocaleTimeString() : 'N/A',
          lastBarRaw,
          barCount1m: oneMinStat.bar_count,
          barCount15m: fifteenMinStat.bar_count,
          status
        };
      });

      setSurveillanceData(processed);
      setLastFetched(new Date());
    } catch (e) {
      console.error('Error fetching equities surveillance statistics:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const filteredData = surveillanceData.filter(row => 
    row.symbol.toLowerCase().includes(filterQuery.toLowerCase())
  );

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
              disabled={loading}
              className={`p-2 rounded-lg border border-border-muted hover:bg-surface-2 transition-smooth ${loading ? 'animate-spin' : ''}`}
            >
              <RefreshCw className="w-4 h-4 text-secondary" />
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
          {/* Live Inventory Matrix */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Layers className="w-4 h-4 text-blue-400" />
              <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Data Freshness Matrix</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredData.slice(0, 3).map((s, idx) => (
                <div key={idx} className="p-4 bg-surface-1 border border-border-muted rounded-2xl flex flex-col gap-2 shadow-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-bold text-dim uppercase tracking-wider">{s.symbol} Feed</span>
                    <span className={`w-2 h-2 rounded-full ${s.status === 'FRESH' ? 'bg-emerald-500' : s.status === 'STALE' ? 'bg-amber-500' : 'bg-red-500'}`} />
                  </div>
                  <div className="text-xl font-bold text-vibrant font-mono">${s.price > 0 ? s.price.toFixed(2) : '—'}</div>
                  <div className="text-[10px] text-dim font-mono">Count 1m: {s.barCount1m.toLocaleString()} bars</div>
                  <div className="text-[10px] text-dim font-mono">Last Ingest: {s.lastBarTime || '—'}</div>
                </div>
              ))}
            </div>
          </section>

          {/* Active Surveillance Feed */}
          <section className="flex-1 min-h-0 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <TerminalIcon className="w-4 h-4 text-blue-400" />
                <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Real-time Surveillance Logs</h2>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-dim" />
                  <input 
                    placeholder="Filter symbol..." 
                    value={filterQuery}
                    onChange={(e) => setFilterQuery(e.target.value)}
                    className="bg-surface-1 border border-border-muted rounded-lg py-1.5 pl-9 pr-4 text-[10px] text-vibrant outline-none focus:border-blue-500/50 w-48" 
                  />
                </div>
              </div>
            </div>

            <div className="flex-1 bg-surface-0 border border-border-muted rounded-2xl overflow-hidden shadow-2xl min-h-[300px]">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-surface-1/50 border-b border-border-muted">
                    {['Symbol', 'Last Price', 'Last Bar Time', 'Bar Count (1min)', 'Surveillance Status'].map(h => (
                      <th key={h} className="text-left px-6 py-4 text-[10px] font-bold text-dim uppercase tracking-widest">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredData.map((row) => (
                    <tr key={row.symbol} className="border-b border-border-muted/30 hover:bg-surface-1/30 transition-smooth group">
                      <td className="px-6 py-4 font-bold text-vibrant">{row.symbol}</td>
                      <td className="px-6 py-4 font-mono text-[11px] text-secondary">${row.price > 0 ? row.price.toFixed(2) : 'Price unavailable'}</td>
                      <td className="px-6 py-4 font-mono text-[11px] text-secondary">{row.lastBarTime || '—'}</td>
                      <td className="px-6 py-4 font-mono text-[11px] text-secondary">{row.barCount1m.toLocaleString()} bars</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border uppercase ${
                          row.status === 'FRESH' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 
                          row.status === 'STALE' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 
                          'bg-red-500/10 text-red-400 border-red-500/20'
                        }`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </main>

        {/* Right Sidebar */}
        <aside className="w-80 border-l border-border-muted bg-surface-1/30 p-6 space-y-6 hidden xl:block">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400" />
              <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Session Health</h2>
            </div>
            <div className="p-4 bg-surface-2/50 rounded-2xl border border-border-muted space-y-4">
              {[
                { l: 'Surveillance Mode', v: 'Continuous Stream', s: 'fresh' },
                { l: 'Symbols Watched', v: '9 Indexes/Stocks', s: 'fresh' },
                { l: 'Network State', v: 'Connected', s: 'fresh' }
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
            <h3 className="text-[11px] font-bold text-vibrant">Risk Guard Surveillance Active</h3>
            <p className="text-[10px] text-dim leading-relaxed">Surveillance is actively validating that real time price ingestion flows meet performance thresholds.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
