export interface TerminalLine {
  type: 'dim' | 'info' | 'ok' | 'warn' | 'error';
  text: string;
}

interface Props {
  lines: TerminalLine[];
  status: 'ready' | 'running' | 'done' | 'error';
  strategyName: string;
}

const TYPE_CLASSES: Record<string, string> = {
  dim:   'text-gray-700',
  info:  'text-blue-400',
  ok:    'text-green-400',
  warn:  'text-amber-400',
  error: 'text-red-400',
};

const STATUS_COLORS: Record<string, string> = {
  ready:   'bg-green-500',
  running: 'bg-blue-500',
  done:    'bg-green-500',
  error:   'bg-red-500',
};

export function TerminalPanel({ lines, status, strategyName }: Props) {
  return (
    <div className="flex flex-col h-full bg-transparent">
      {/* Output */}
      <div className="flex-1 overflow-y-auto px-4 py-2 font-mono text-[11px] leading-relaxed space-y-0.5 custom-scrollbar">
        {lines.map((l, i) => (
          <div key={i} className={`flex gap-3 ${TYPE_CLASSES[l.type] || 'text-primary'}`}>
            <span className="text-dim opacity-50 select-none">{(i + 1).toString().padStart(2, '0')}</span>
            <span className="break-all">{l.text}</span>
          </div>
        ))}
        {status === 'running' && (
          <div className="flex gap-3">
             <span className="text-dim opacity-50 select-none">{(lines.length + 1).toString().padStart(2, '0')}</span>
             <span className="inline-block w-1.5 h-3.5 bg-blue-500 align-text-bottom animate-pulse" />
          </div>
        )}
      </div>
    </div>
  );
}
