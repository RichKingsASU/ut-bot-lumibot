import { useRef } from 'react';

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

const STATUS_BADGES: Record<string, { label: string; className: string }> = {
  active:   { label: 'Active',    className: 'bg-green-950 text-green-400 border border-green-900' },
  deployed: { label: 'Deployed',  className: 'bg-blue-950 text-blue-400 border border-blue-900' },
  draft:    { label: 'Draft',     className: 'bg-amber-950 text-amber-400 border border-amber-900' },
  archived: { label: 'Archived',  className: 'bg-gray-900 text-gray-500 border border-gray-800' },
};

export function StrategyLibrary({ strategies, selectedId, onSelect, onUpload }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);

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
    <div className="flex flex-col h-full bg-[#0f141a] border-r border-gray-800">
      {/* Header */}
      <div className="p-3 border-b border-gray-800">
        <span className="block text-[9px] font-bold text-gray-600 uppercase tracking-widest mb-3">
          Strategy Library
        </span>
        {/* Search */}
        <div className="flex items-center gap-2 bg-[#060810] border border-gray-800 rounded px-2 py-1.5 mb-2">
          <svg className="w-3 h-3 text-gray-700 flex-shrink-0" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="5" cy="5" r="3.5"/><line x1="7.5" y1="7.5" x2="11" y2="11"/>
          </svg>
          <input
            className="bg-transparent border-none outline-none text-xs text-gray-300 placeholder-gray-700 w-full"
            placeholder="Search systems..."
          />
        </div>
        {/* Upload */}
        <button
          onClick={() => fileRef.current?.click()}
          className="w-full flex items-center justify-center gap-1.5 py-1.5 bg-[#111420] border border-gray-800 rounded text-[10px] font-semibold text-gray-400 hover:border-gray-700 hover:text-gray-200 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M6 8V2M3 5l3-3 3 3"/><path d="M1 9v1a1 1 0 001 1h8a1 1 0 001-1V9"/>
          </svg>
          Upload Strategy
        </button>
        <input ref={fileRef} type="file" accept=".py,.json" className="hidden" onChange={handleFileChange} />
      </div>

      {/* Strategy list */}
      <div className="flex-1 overflow-y-auto">
        {strategies.map((s) => {
          const isSelected = s.id === selectedId;
          const badge = STATUS_BADGES[s.status];
          return (
            <div
              key={s.id}
              onClick={() => onSelect(s)}
              className={`px-3 py-2.5 cursor-pointer border-l-2 transition-all ${
                isSelected
                  ? 'bg-[#111420] border-l-blue-500'
                  : 'border-l-transparent hover:bg-[#111420]'
              } ${s.status === 'archived' ? 'opacity-60' : ''}`}
            >
              <div className={`text-xs font-semibold ${isSelected ? 'text-blue-400' : 'text-gray-400'}`}>
                {s.name}
              </div>
              <div className="text-[9px] text-gray-600 mt-0.5">{s.language} · {s.status.charAt(0).toUpperCase() + s.status.slice(1)}</div>
              <div className="flex gap-1 mt-1 flex-wrap">
                <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${badge.className}`}>
                  {badge.label}
                </span>
                {isSelected && s.status !== 'archived' && (
                  <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-900">
                    Deployed
                  </span>
                )}
                {s.isCrypto && (
                  <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-purple-950 text-purple-400 border border-purple-900">
                    Crypto
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
