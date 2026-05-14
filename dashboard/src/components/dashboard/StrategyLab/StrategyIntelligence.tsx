import React from 'react';
import { motion } from 'framer-motion';
import { Brain, Zap, AlertTriangle, TrendingUp, Info } from 'lucide-react';

interface Props {
  strategyName: string;
  insights: {
    type: 'positive' | 'neutral' | 'negative' | 'warning';
    label: string;
    description: string;
  }[];
  confidenceScore: number;
}

export const StrategyIntelligence: React.FC<Props> = ({ strategyName, insights, confidenceScore }) => {
  return (
    <div className="flex flex-col gap-4 p-4 glass-panel rounded-xl shadow-premium">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <Brain className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-vibrant">Strategy Intelligence</h3>
            <p className="text-[10px] text-secondary">AI-Native Reasoning for {strategyName}</p>
          </div>
        </div>
        <div className="flex flex-col items-end">
          <div className="text-[10px] font-bold text-secondary uppercase tracking-widest">Confidence</div>
          <div className="text-xl font-mono font-bold text-gradient-blue">{confidenceScore}%</div>
        </div>
      </div>

      <div className="space-y-3 mt-2">
        {insights.map((insight, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.1 }}
            className="flex gap-3 p-3 bg-surface-2/50 rounded-lg border border-border-muted hover:border-border-active transition-smooth group"
          >
            <div className="mt-0.5">
              {insight.type === 'positive' && <TrendingUp className="w-4 h-4 text-emerald-400" />}
              {insight.type === 'negative' && <Zap className="w-4 h-4 text-rose-400" />}
              {insight.type === 'warning' && <AlertTriangle className="w-4 h-4 text-amber-400" />}
              {insight.type === 'neutral' && <Info className="w-4 h-4 text-blue-400" />}
            </div>
            <div>
              <div className="text-[11px] font-bold text-vibrant group-hover:text-blue-400 transition-colors">
                {insight.label}
              </div>
              <p className="text-[10px] text-secondary leading-relaxed mt-1">
                {insight.description}
              </p>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="mt-2 pt-3 border-t border-border-muted">
        <button className="w-full py-2 bg-blue-600/10 hover:bg-blue-600/20 border border-blue-500/30 rounded-lg text-[10px] font-bold text-blue-400 transition-smooth uppercase tracking-widest">
          Request Deeper Analysis
        </button>
      </div>
    </div>
  );
};
