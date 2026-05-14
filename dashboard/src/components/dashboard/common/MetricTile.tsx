import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Activity, Clock } from 'lucide-react';

interface Props {
  label: string;
  value: string | number;
  change?: string | number;
  isPositive?: boolean;
  status?: 'fresh' | 'stale' | 'none';
  icon?: React.ElementType;
  sparkline?: string; // SVG path or simplified data
}

export const MetricTile: React.FC<Props> = ({ label, value, change, isPositive, status, icon: Icon, sparkline }) => {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-4 glass-panel rounded-2xl shadow-premium hover:border-border-active transition-smooth group relative overflow-hidden"
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center gap-2">
          {Icon ? (
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Icon className="w-4 h-4 text-blue-400" />
            </div>
          ) : (
            <div className="p-2 bg-zinc-500/10 rounded-lg">
              <Activity className="w-4 h-4 text-secondary" />
            </div>
          )}
          <span className="text-[10px] font-bold text-secondary uppercase tracking-[0.1em]">{label}</span>
        </div>
        {status && (
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[9px] font-bold ${
            status === 'fresh' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
            status === 'stale' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
            'bg-zinc-500/10 text-dim border-zinc-500/20'
          }`}>
            <span className={`w-1 h-1 rounded-full ${
              status === 'fresh' ? 'bg-emerald-400 pulse-dot' :
              status === 'stale' ? 'bg-amber-400' :
              'bg-zinc-500'
            }`} />
            {status.toUpperCase()}
          </div>
        )}
      </div>

      <div className="flex items-end justify-between">
        <div className="space-y-1">
          <div className="text-2xl font-mono font-bold text-vibrant tracking-tight">
            {value}
          </div>
          {change && (
            <div className={`flex items-center gap-1 text-xs font-bold ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {change}
            </div>
          )}
        </div>
        
        {sparkline && (
          <div className="w-20 h-10 overflow-hidden">
            <svg width="100%" height="100%" viewBox="0 0 100 40" preserveAspectRatio="none">
              <motion.path
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 1, ease: "easeOut" }}
                d={sparkline}
                fill="none"
                stroke={isPositive ? '#10b981' : '#ef4444'}
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </div>
        )}
      </div>

      {/* Subtle bottom accent */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-blue-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-smooth" />
    </motion.div>
  );
};
