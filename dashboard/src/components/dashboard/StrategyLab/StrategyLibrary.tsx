import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Plus, FileCode, Clock, CheckCircle2, AlertCircle, Archive, MoreHorizontal, Upload, Zap, BookOpen } from 'lucide-react';
import { supabase } from '../../../lib/supabaseClient';

export interface LabStrategy {
  id: string;
  name: string;
  filename: string;
  language: string;
  status: 'active' | 'draft' | 'deployed' | 'archived';
  isCrypto?: boolean;
  code: string;
  lastSaved?: string;
  created_at?: string;
  description?: string;
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

const DEFAULT_FALLBACKS: LabStrategy[] = [
  {
    id: 'fallback-1',
    name: 'AdaptiveTrendMR ETH',
    filename: 'adaptive_trend_mr_eth.py',
    language: 'Python',
    status: 'active',
    isCrypto: true,
    code: '# Deployed AdaptiveTrendMR ETH',
    lastSaved: 'Active',
    created_at: new Date().toISOString(),
    description: 'Crypto adaptive momentum strategy on Ethereum'
  },
  {
    id: 'fallback-2',
    name: 'UTBot SPY',
    filename: 'utbot_paper_trader.py',
    language: 'Python',
    status: 'active',
    isCrypto: false,
    code: '# Deployed UTBot SPY',
    lastSaved: 'Active',
    created_at: new Date().toISOString(),
    description: 'Equities ATR scalper strategy on SPY index'
  }
];

export function StrategyLibrary({ strategies: propsStrategies, selectedId, onSelect, onUpload }: Props) {
  const [search, setSearch] = useState('');
  const [dbStrategies, setDbStrategies] = useState<LabStrategy[]>([]);
  const [isUsingFallback, setIsUsingFallback] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchStrategies = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from('strategies')
        .select('id, name, filename, language, status, is_crypto, created_at, description, params')
        .order('created_at', { ascending: false });

      if (error) throw error;

      if (!data || data.length === 0) {
        setDbStrategies(DEFAULT_FALLBACKS);
        setIsUsingFallback(true);
      } else {
        const mapped = data.map((r: any) => {
          const params = r.params || {};
          return {
            id: String(r.id),
            name: r.name || 'Untitled',
            filename: r.filename || params.filename || `${(r.name || 'untitled').toLowerCase().replace(/\s+/g, '_')}.py`,
            language: r.language || 'Python',
            status: (r.status || params.status || 'draft') as LabStrategy['status'],
            isCrypto: r.is_crypto !== undefined ? r.is_crypto : (params.is_crypto || false),
            code: params.code || '',
            lastSaved: r.created_at ? `Created ${new Date(r.created_at).toLocaleDateString()}` : 'Saved',
            created_at: r.created_at,
            description: r.description || ''
          };
        });
        setDbStrategies(mapped);
        setIsUsingFallback(false);
      }
    } catch (e) {
      console.warn('Error querying strategies table, falling back to defaults:', e);
      setDbStrategies(DEFAULT_FALLBACKS);
      setIsUsingFallback(true);
    }
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const mergedStrategies = useMemo(() => {
    // Dedup by id preferring dbStrategies
    const map = new Map<string, LabStrategy>();
    DEFAULT_FALLBACKS.forEach(s => map.set(s.id, s));
    dbStrategies.forEach(s => map.set(s.id, s));
    propsStrategies.forEach(s => map.set(s.id, s));
    return Array.from(map.values());
  }, [dbStrategies, propsStrategies]);

  const filteredStrategies = useMemo(() => {
    return mergedStrategies.filter(s => 
      s.name.toLowerCase().includes(search.toLowerCase()) || 
      s.filename.toLowerCase().includes(search.toLowerCase())
    );
  }, [mergedStrategies, search]);

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
          <h2 className="text-[10px] font-bold text-secondary uppercase tracking-[0.2em] flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-blue-400" />
            Strategy Library
          </h2>
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

        {isUsingFallback && (
          <div className="p-2 bg-blue-500/10 border border-blue-500/20 rounded-lg text-[10px] text-blue-400">
            Showing deployed strategies — upload more in Strategy Lab
          </div>
        )}
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
                    <div className="text-[10px] text-dim truncate font-mono mt-0.5">{s.filename}</div>
                    
                    <div className="flex flex-wrap items-center gap-1.5 mt-2">
                      <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md border uppercase ${statusColor}`}>
                        {s.status}
                      </span>
                      <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-md border border-blue-500/25 bg-blue-500/5 text-blue-400">
                        {s.isCrypto ? 'CRYPTO' : 'EQUITIES'}
                      </span>
                      <span className="text-[8px] font-bold px-1.5 py-0.5 rounded-md border border-zinc-500/20 bg-zinc-500/5 text-zinc-400">
                        {s.language.toUpperCase()}
                      </span>
                    </div>
                    
                    {s.created_at && (
                      <div className="text-[9px] text-dim mt-2 flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {new Date(s.created_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                  <button className="opacity-0 group-hover:opacity-100 p-1 hover:bg-surface-2 rounded transition-smooth">
                    <MoreHorizontal className="w-4 h-4 text-dim" />
                  </button>
                </div>
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
