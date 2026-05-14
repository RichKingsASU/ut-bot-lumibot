import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '../../../lib/supabaseClient';
import { PageHeader } from '../../ui/PageHeader';
import { MetricTile } from '../common/MetricTile';
import { 
  ShieldAlert, ShieldCheck, ZapOff, 
  Settings2, Activity, Save, 
  AlertTriangle, History, Info,
  Unlock, Lock, Trash2
} from 'lucide-react';

const MAX_DAILY_LOSS_CAP = 1_000_000;

interface RiskState {
  trading_enabled: boolean;
  max_daily_loss: number;
  max_position_pct: number;
  account_equity: number;
}

export default function RiskManagerView() {
    const [state, setState] = useState<RiskState>({
        trading_enabled: true,
        max_daily_loss: 500,
        max_position_pct: 10,
        account_equity: 100000
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [isKillSwitchLocked, setIsKillSwitchLocked] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const { data } = await supabase
                    .from('user_settings')
                    .select('*')
                    .eq('id', 1)
                    .single();
                if (data) {
                    setState({
                        trading_enabled: data.trading_enabled ?? true,
                        max_daily_loss: data.max_daily_loss ?? 500,
                        max_position_pct: data.max_position_pct ?? 10,
                        account_equity: data.account_equity ?? 100000
                    });
                }
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    const toggleKillSwitch = async () => {
        if (isKillSwitchLocked) return;
        const newVal = !state.trading_enabled;
        setState(prev => ({ ...prev, trading_enabled: newVal }));
        try {
            await supabase
                .from('user_settings')
                .upsert({ id: 1, trading_enabled: newVal }, { onConflict: 'id' });
        } catch (e) {
            console.error(e);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await supabase
                .from('user_settings')
                .upsert({
                    id: 1,
                    max_daily_loss: state.max_daily_loss,
                    max_position_pct: state.max_position_pct
                }, { onConflict: 'id' });
        } catch (e) {
            console.error(e);
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <div className="p-8 text-dim animate-pulse">Initializing Risk Engine...</div>;

    return (
        <div className="flex flex-col h-full bg-space overflow-hidden">
            {/* Header */}
            <div className="p-6 bg-surface-1/50 border-b border-border-muted backdrop-blur-md">
                <div className="flex items-center justify-between">
                    <PageHeader 
                        title="Risk Control Tower" 
                        subtitle="Institutional Safety Guards & Interventions" 
                    />
                    <div className="flex items-center gap-3">
                         <div className={`px-3 py-1.5 rounded-full border text-[10px] font-bold flex items-center gap-2 ${
                            state.trading_enabled 
                                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                                : 'bg-rose-500/10 text-rose-400 border-rose-500/20 shadow-[0_0_20px_rgba(239,68,68,0.2)]'
                         }`}>
                            <div className={`w-1.5 h-1.5 rounded-full ${state.trading_enabled ? 'bg-emerald-500 pulse-dot' : 'bg-rose-500'}`} />
                            {state.trading_enabled ? 'OPERATIONAL' : 'HALTED'}
                         </div>
                    </div>
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden">
                <main className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
                    
                    {/* Emergency Control Hub */}
                    <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Master Kill Switch */}
                        <div className={`p-6 rounded-2xl border transition-smooth relative overflow-hidden group ${
                            state.trading_enabled 
                                ? 'bg-surface-1 border-border-muted hover:border-emerald-500/30' 
                                : 'bg-rose-500/5 border-rose-500/40 shadow-[0_0_40px_rgba(239,68,68,0.1)]'
                        }`}>
                            <div className="flex items-center justify-between mb-6 relative z-10">
                                <div className="flex items-center gap-3">
                                    <div className={`p-3 rounded-xl ${state.trading_enabled ? 'bg-zinc-500/10' : 'bg-rose-500/20'}`}>
                                        {state.trading_enabled ? <ShieldCheck className="w-6 h-6 text-emerald-400" /> : <ZapOff className="w-6 h-6 text-rose-400" />}
                                    </div>
                                    <div>
                                        <h3 className="text-sm font-bold text-vibrant uppercase tracking-widest">Master Kill Switch</h3>
                                        <p className="text-[10px] text-secondary">Instant Halt of All Trading Activity</p>
                                    </div>
                                </div>
                                <button 
                                    onClick={() => setIsKillSwitchLocked(!isKillSwitchLocked)}
                                    className={`p-2 rounded-lg transition-smooth border ${isKillSwitchLocked ? 'bg-zinc-500/10 border-border-muted text-dim' : 'bg-blue-500/20 border-blue-500/40 text-blue-400 animate-pulse'}`}
                                >
                                    {isKillSwitchLocked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                                </button>
                            </div>

                            <button 
                                onClick={toggleKillSwitch}
                                disabled={isKillSwitchLocked}
                                className={`w-full py-4 rounded-xl font-bold uppercase tracking-[0.2em] transition-smooth border shadow-2xl ${
                                    isKillSwitchLocked 
                                        ? 'bg-zinc-800/50 border-border-muted text-dim cursor-not-allowed' 
                                        : state.trading_enabled 
                                            ? 'bg-rose-600 hover:bg-rose-500 border-rose-400 text-white shadow-rose-900/40' 
                                            : 'bg-emerald-600 hover:bg-emerald-500 border-emerald-400 text-white shadow-emerald-900/40'
                                }`}
                            >
                                {state.trading_enabled ? 'TRIGGER SYSTEM HALT' : 'RE-AUTHORIZE SYSTEM'}
                            </button>
                            
                            {isKillSwitchLocked && (
                                <p className="text-[9px] text-center mt-3 text-dim font-bold uppercase tracking-widest">Toggle Lock to Interface</p>
                            )}
                        </div>

                        {/* Liquidation & Panic */}
                        <div className="p-6 bg-surface-1 border border-border-muted rounded-2xl hover:border-rose-500/30 transition-smooth group flex flex-col justify-between">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="p-3 bg-rose-500/10 rounded-xl">
                                    <Trash2 className="w-6 h-6 text-rose-400" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-bold text-vibrant uppercase tracking-widest">Panic Liquidation</h3>
                                    <p className="text-[10px] text-secondary">Force Exit All Active Positions</p>
                                </div>
                            </div>
                            
                            <div className="p-3 bg-surface-0 rounded-xl border border-border-muted mb-4">
                                <div className="flex justify-between items-center text-[10px] mb-1">
                                    <span className="text-dim font-bold uppercase">Exposure Risk</span>
                                    <span className="text-rose-400 font-bold">$12,480.00</span>
                                </div>
                                <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                                    <motion.div className="h-full bg-rose-500" initial={{ width: 0 }} animate={{ width: '42%' }} />
                                </div>
                            </div>

                            <button className="w-full py-3 bg-transparent hover:bg-rose-500/10 border border-rose-500/40 text-rose-400 rounded-xl font-bold text-xs uppercase tracking-widest transition-smooth">
                                Force Global Liquidation
                            </button>
                        </div>
                    </section>

                    {/* Risk Rules Engine */}
                    <section>
                        <div className="flex items-center gap-2 mb-4">
                            <Settings2 className="w-4 h-4 text-blue-400" />
                            <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Risk Rules Engine</h2>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Daily Loss Limit */}
                            <div className="p-6 bg-surface-1 border border-border-muted rounded-2xl space-y-4 shadow-premium group">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                                        <span className="text-xs font-bold text-vibrant">Daily Drawdown Cap</span>
                                    </div>
                                    <Info className="w-3.5 h-3.5 text-dim cursor-help" />
                                </div>
                                <div className="relative">
                                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-xs text-dim font-mono">$</span>
                                    <input 
                                        type="number"
                                        value={state.max_daily_loss}
                                        onChange={e => setState(prev => ({ ...prev, max_daily_loss: parseFloat(e.target.value) }))}
                                        className="w-full bg-surface-0 border border-border-muted rounded-xl py-3 pl-8 pr-4 text-sm font-mono text-vibrant outline-none focus:border-blue-500/50 transition-smooth"
                                    />
                                </div>
                                <div className="flex justify-between items-center text-[10px] text-dim font-bold uppercase">
                                    <span>Safe Limit: $10k</span>
                                    <span className={state.max_daily_loss > 5000 ? 'text-rose-400' : 'text-emerald-400'}>
                                        {state.max_daily_loss > 5000 ? 'HIGH RISK' : 'CONSERVATIVE'}
                                    </span>
                                </div>
                                <div className="h-1 bg-surface-2 rounded-full overflow-hidden">
                                    <motion.div 
                                        className={`h-full ${state.max_daily_loss > 5000 ? 'bg-rose-500' : 'bg-emerald-500'}`} 
                                        initial={{ width: 0 }} 
                                        animate={{ width: `${Math.min((state.max_daily_loss / 10000) * 100, 100)}%` }} 
                                    />
                                </div>
                            </div>

                            {/* Max Position Pct */}
                            <div className="p-6 bg-surface-1 border border-border-muted rounded-2xl space-y-4 shadow-premium group">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Activity className="w-4 h-4 text-blue-400" />
                                        <span className="text-xs font-bold text-vibrant">Max Position Allocation</span>
                                    </div>
                                    <Info className="w-3.5 h-3.5 text-dim cursor-help" />
                                </div>
                                <div className="relative">
                                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-dim font-mono">%</span>
                                    <input 
                                        type="number"
                                        value={state.max_position_pct}
                                        onChange={e => setState(prev => ({ ...prev, max_position_pct: parseFloat(e.target.value) }))}
                                        className="w-full bg-surface-0 border border-border-muted rounded-xl py-3 pl-4 pr-10 text-sm font-mono text-vibrant outline-none focus:border-blue-500/50 transition-smooth"
                                    />
                                </div>
                                <div className="flex justify-between items-center text-[10px] text-dim font-bold uppercase">
                                    <span>Limit: 1-100%</span>
                                    <span className={state.max_position_pct > 25 ? 'text-rose-400' : 'text-emerald-400'}>
                                        {state.max_position_pct > 25 ? 'AGGRESSIVE' : 'OPTIMAL'}
                                    </span>
                                </div>
                                <div className="h-1 bg-surface-2 rounded-full overflow-hidden">
                                    <motion.div 
                                        className={`h-full ${state.max_position_pct > 25 ? 'bg-rose-500' : 'bg-emerald-500'}`} 
                                        initial={{ width: 0 }} 
                                        animate={{ width: `${state.max_position_pct}%` }} 
                                    />
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Risk Audit Trail */}
                    <section>
                         <div className="flex items-center gap-2 mb-4">
                            <History className="w-4 h-4 text-secondary" />
                            <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Risk Intervention Audit</h2>
                        </div>
                        <div className="bg-surface-0 border border-border-muted rounded-2xl overflow-hidden shadow-2xl">
                            <table className="w-full text-left">
                                <thead className="bg-surface-1/50 border-b border-border-muted">
                                    <tr>
                                        {['Timestamp', 'User', 'Action', 'Status'].map(h => (
                                            <th key={h} className="px-6 py-3 text-[9px] font-bold text-dim uppercase tracking-widest">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="text-[11px]">
                                    <tr className="border-b border-border-muted/30">
                                        <td className="px-6 py-4 text-secondary font-mono">2026-05-13 22:42:11</td>
                                        <td className="px-6 py-4 text-vibrant font-bold">Admin</td>
                                        <td className="px-6 py-4 text-secondary">Updated Max Daily Loss: $500 → $800</td>
                                        <td className="px-6 py-4"><span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20">SUCCESS</span></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </section>
                </main>

                {/* Fixed Footer for Save */}
                <div className="fixed bottom-6 right-6 z-30">
                    <button 
                        onClick={handleSave}
                        disabled={saving}
                        className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold shadow-2xl shadow-blue-900/40 transition-smooth group"
                    >
                        <Save className={`w-4 h-4 ${saving ? 'animate-spin' : 'group-hover:scale-110 transition-transform'}`} />
                        {saving ? 'UPDATING...' : 'SAVE RISK PROFILE'}
                    </button>
                </div>

                {/* Right Analytics Sidebar */}
                <aside className="w-80 border-l border-border-muted bg-surface-1/30 p-6 space-y-8 hidden xl:block">
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <ShieldAlert className="w-4 h-4 text-rose-400" />
                            <h2 className="text-[11px] font-bold text-secondary uppercase tracking-[0.2em]">Active Exposure</h2>
                        </div>
                        <div className="space-y-4">
                            <MetricTile label="Total Value at Risk" value="$12,480" change="-12% from cap" isPositive={true} />
                            <MetricTile label="Margin Usage" value="8.4%" change="OPTIMAL" isPositive={true} status="fresh" />
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    );
}
