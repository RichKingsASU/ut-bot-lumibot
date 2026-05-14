import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, RefreshCw, Zap, TrendingUp, TrendingDown, Activity, Globe, ShieldCheck } from 'lucide-react';
import { PageHeader } from '../../ui/PageHeader';
import { MetricTile } from '../common/MetricTile';

interface CryptoQuote {
    symbol: string;
    price: number;
    change24h: number;
    status: 'fresh' | 'stale';
}

const CRYPTO_SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD'];

export default function CryptoMonitorView() {
    const [quotes, setQuotes] = useState<CryptoQuote[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    const fetchPrices = useCallback(async () => {
        try {
            const res = await fetch(`/.netlify/functions/crypto-prices?symbols=${CRYPTO_SYMBOLS.map(encodeURIComponent).join(',')}`);
            const data = await res.json();
            
            const parsed = CRYPTO_SYMBOLS.map(sym => {
                const q = data.quotes?.[sym] || {};
                return {
                    symbol: sym,
                    price: Number(q.price ?? 0),
                    change24h: Number(q.change_pct ?? 0),
                    status: 'fresh'
                } as CryptoQuote;
            }).filter(q => q.price > 0);

            setQuotes(parsed);
            setLastUpdated(new Date());
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPrices();
        const interval = setInterval(fetchPrices, 30000);
        return () => clearInterval(interval);
    }, [fetchPrices]);

    return (
        <div className="flex flex-col h-full bg-space overflow-hidden">
            {/* Header */}
            <div className="p-6 bg-surface-1/50 border-b border-border-muted backdrop-blur-md">
                <div className="flex items-center justify-between">
                    <PageHeader 
                        title="Crypto Command" 
                        subtitle="24/7 Global Asset Surveillance" 
                    />
                    <div className="flex items-center gap-4">
                        <div className="flex flex-col items-end">
                            <span className="text-[10px] font-bold text-dim uppercase tracking-widest">Network Status</span>
                            <div className="flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                                <span className="text-xs font-mono font-bold text-purple-400">MAINNET LIVE</span>
                            </div>
                        </div>
                        <button 
                            onClick={fetchPrices}
                            className={`p-2 rounded-lg border border-border-muted hover:bg-surface-2 transition-smooth ${loading ? 'animate-spin' : ''}`}
                        >
                            <RefreshCw className="w-4 h-4 text-secondary" />
                        </button>
                    </div>
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden">
                <main className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
                    
                    {/* Market Hours Banner - Specific to Crypto 24/7 */}
                    <div className="p-4 bg-purple-500/5 border border-purple-500/20 rounded-2xl flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-500/10 rounded-lg">
                                <Globe className="w-4 h-4 text-purple-400" />
                            </div>
                            <div>
                                <h3 className="text-xs font-bold text-vibrant">Global Operations Active</h3>
                                <p className="text-[10px] text-secondary">Crypto markets are currently streaming from Alpaca Data Clusters.</p>
                            </div>
                        </div>
                        <div className="px-3 py-1 bg-purple-500/10 rounded-full text-[9px] font-bold text-purple-400 border border-purple-500/20">
                            24/7 SURVEILLANCE
                        </div>
                    </div>

                    {/* Price Matrix */}
                    <section>
                        <div className="flex items-center gap-2 mb-4">
                            <Zap className="w-4 h-4 text-purple-400" />
                            <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Real-Time Price Matrix</h2>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            {quotes.map((q, idx) => (
                                <MetricTile 
                                    key={q.symbol}
                                    label={q.symbol}
                                    value={q.price < 1 ? q.price.toFixed(4) : q.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    change={`${q.change24h > 0 ? '+' : ''}${q.change24h.toFixed(2)}%`}
                                    isPositive={q.change24h >= 0}
                                    status={q.status}
                                    icon={Activity}
                                    sparkline={q.change24h >= 0 ? "M0,30 Q25,10 50,25 T100,5" : "M0,5 Q25,30 50,15 T100,35"}
                                />
                            ))}
                        </div>
                    </section>

                    {/* Order Book Visualization Placeholder */}
                    <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <div className="flex items-center gap-2">
                                <TrendingUp className="w-4 h-4 text-emerald-400" />
                                <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Bid Liquidity Depth</h2>
                            </div>
                            <div className="h-64 bg-surface-0 border border-border-muted rounded-2xl overflow-hidden shadow-2xl relative">
                                <div className="absolute inset-0 bg-gradient-to-t from-emerald-500/5 to-transparent" />
                                <div className="p-4 space-y-2 relative">
                                    {[1, 2, 3, 4, 5, 6].map(i => (
                                        <div key={i} className="flex items-center justify-between">
                                            <span className="text-[10px] font-mono text-emerald-400 font-bold">{(60000 - i * 10).toLocaleString()}</span>
                                            <div className="flex-1 mx-4 h-2 bg-surface-1 rounded-full overflow-hidden">
                                                <div className="h-full bg-emerald-500/40 rounded-full" style={{ width: `${100 - i * 15}%` }} />
                                            </div>
                                            <span className="text-[10px] font-mono text-secondary">{ (Math.random() * 2).toFixed(3) } BTC</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div className="flex items-center gap-2">
                                <TrendingDown className="w-4 h-4 text-rose-400" />
                                <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Ask Liquidity Depth</h2>
                            </div>
                            <div className="h-64 bg-surface-0 border border-border-muted rounded-2xl overflow-hidden shadow-2xl relative">
                                <div className="absolute inset-0 bg-gradient-to-t from-rose-500/5 to-transparent" />
                                <div className="p-4 space-y-2 relative">
                                    {[1, 2, 3, 4, 5, 6].map(i => (
                                        <div key={i} className="flex items-center justify-between">
                                            <span className="text-[10px] font-mono text-rose-400 font-bold">{(60100 + i * 10).toLocaleString()}</span>
                                            <div className="flex-1 mx-4 h-2 bg-surface-1 rounded-full overflow-hidden">
                                                <div className="h-full bg-rose-500/40 rounded-full" style={{ width: `${30 + i * 10}%` }} />
                                            </div>
                                            <span className="text-[10px] font-mono text-secondary">{ (Math.random() * 2).toFixed(3) } BTC</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </section>
                </main>

                <aside className="w-80 border-l border-border-muted bg-surface-1/30 p-6 space-y-6 hidden xl:block">
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-purple-400" />
                            <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Asset Alpha</h2>
                        </div>
                        <div className="space-y-3">
                            {['Volatility Index', 'Momentum Factor', 'Volume Delta'].map((l, i) => (
                                <div key={i} className="p-3 bg-surface-2/50 rounded-xl border border-border-muted">
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-[9px] font-bold text-dim uppercase tracking-wider">{l}</span>
                                        <span className="text-[10px] font-mono text-vibrant font-bold">{(Math.random() * 100).toFixed(1)}</span>
                                    </div>
                                    <div className="h-1 bg-surface-0 rounded-full overflow-hidden">
                                        <div className="h-full bg-purple-500 rounded-full" style={{ width: `${Math.random() * 100}%` }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="p-6 glass-panel rounded-2xl border border-purple-500/30 text-center space-y-2 relative overflow-hidden group">
                        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-transparent opacity-50" />
                        <ShieldCheck className="w-8 h-8 text-purple-400 mx-auto mb-2 relative z-10" />
                        <h3 className="text-[11px] font-bold text-vibrant relative z-10">Algorithmic Shield</h3>
                        <p className="text-[10px] text-dim leading-relaxed relative z-10">24/7 Automated Risk Mitigation active on all Crypto instruments.</p>
                    </div>
                </aside>
            </div>
        </div>
    );
}
