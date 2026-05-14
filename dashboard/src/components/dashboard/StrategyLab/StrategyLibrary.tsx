import React, { useState, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Plus, FileCode, Clock, CheckCircle2, AlertCircle, Archive, MoreHorizontal, Upload, Zap } from 'lucide-react';

export interface LabStrategy {
  id: string;
  name: string;
  filename: string;
  language: string;
  status: 'active' | 'draft' | 'deployed' | 'archived';
  isCrypto?: boolean;
  code: string;
  lastSaved?: string;
  backtestResult?: {
    totalReturn: string;
    sharpe: string;
    winRate: string;
    maxDrawdown: string;
    vol: string;
    version: string;
    curve: string;
  };
}

interface Props {
  strategies: LabStrategy[];
  selectedId: string;
  onSelect: (s: LabStrategy) => void;
  onUpload: (code: string, filename: string) => void;
}

const STATUS_ICONS: Record<string, React.ElementType> = {
  active:   CheckCircle2,
  deployed: Zap,
  draft:    FileCode,
  archived: Archive,
};

const STATUS_COLORS: Record<string, string> = {
  active:   'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  deployed: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  draft:    'text-amber-400 bg-amber-500/10 border-amber-500/20',
  archived: 'text-zinc-500 bg-zinc-500/10 border-zinc-500/20',
};

export function StrategyLibrary({ strategies, selectedId, onSelect, onUpload }: Props) {
  const [search, setSearch] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const filteredStrategies = useMemo(() => {
    return strategies.filter(s => 
      s.name.toLowerCase().includes(search.toLowerCase()) || 
      s.filename.toLowerCase().includes(search.toLowerCase())
    );
  }, [strategies, search]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const code = ev.target?.result as string;
      onUpload(code, file.name);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  return (
    <div className="flex flex-col h-full bg-surface-0 border-r border-border-muted">
      {/* Header */}
      <div className="p-4 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-[10px] font-bold text-secondary uppercase tracking-[0.2em]">Strategy Library</h2>
          <button 
            onClick={() => fileRef.current?.click()}
            className="p-1.5 hover:bg-surface-2 rounded-md transition-smooth text-secondary hover:text-vibrant"
            title="Upload Strategy"
          >
            <Plus className="w-4 h-4" />
          </button>
          <input ref={fileRef} type="file" accept=".py,.json" className="hidden" onChange={handleFileChange} />
        </div>

        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-dim group-focus-within:text-blue-400 transition-colors" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search systems..."
            className="w-full bg-surface-1 border border-border-muted rounded-lg py-2 pl-9 pr-4 text-xs text-vibrant placeholder-dim outline-none focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/5 transition-smooth"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
        <AnimatePresence mode="popLayout">
          {filteredStrategies.map((s) => {
            const isSelected = s.id === selectedId;
            const Icon = STATUS_ICONS[s.status] || FileCode;
            const statusColor = STATUS_COLORS[s.status];

            return (
              <motion.div
                key={s.id}
                layout
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                onClick={() => onSelect(s)}
                className={`group relative p-3 rounded-xl cursor-pointer transition-smooth ${
                  isSelected 
                    ? 'bg-surface-2 shadow-premium' 
                    : 'hover:bg-surface-1'
                }`}
              >
                {isSelected && (
                  <motion.div 
                    layoutId="active-indicator"
                    className="absolute left-0 top-3 bottom-3 w-1 bg-blue-500 rounded-full"
                  />
                )}
                
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className={`text-[13px] font-semibold truncate ${isSelected ? 'text-vibrant' : 'text-primary group-hover:text-vibrant'}`}>
                      {s.name}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-md border ${statusColor}`}>
                        {s.status.toUpperCase()}
                      </span>
                      <span className="text-[10px] text-dim flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {s.lastSaved?.includes('saved') ? s.lastSaved.replace('Last saved ', '') : 'Draft'}
                      </span>
                    </div>
                  </div>
                  <button className="opacity-0 group-hover:opacity-100 p-1 hover:bg-surface-2 rounded transition-smooth">
                    <MoreHorizontal className="w-4 h-4 text-dim" />
                  </button>
                </div>

                {isSelected && s.backtestResult && (
                  <motion.div 
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="mt-3 pt-3 border-t border-border-muted"
                  >
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-surface-0/50 p-1.5 rounded-lg border border-border-muted">
                        <div className="text-[8px] text-dim uppercase">Return</div>
                        <div className="text-[11px] font-mono font-bold text-emerald-400">{s.backtestResult.totalReturn}</div>
                      </div>
                      <div className="bg-surface-0/50 p-1.5 rounded-lg border border-border-muted">
                        <div className="text-[8px] text-dim uppercase">Sharpe</div>
                        <div className="text-[11px] font-mono font-bold text-vibrant">{s.backtestResult.sharpe}</div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-border-muted bg-surface-1/50">
        <button 
          onClick={() => fileRef.current?.click()}
          className="w-full flex items-center justify-center gap-2 py-2 bg-vibrant text-space rounded-lg text-[11px] font-bold hover:bg-blue-400 transition-smooth"
        >
          <Upload className="w-3.5 h-3.5" />
          Import Module
        </button>
      </div>
    </div>
  );
}
