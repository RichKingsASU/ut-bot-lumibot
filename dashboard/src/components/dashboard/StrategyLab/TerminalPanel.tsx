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
    <div className="flex flex-col h-full bg-[#060810] border-t border-gray-800">
      {/* Bar */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[#0d0f1a] border-b border-gray-800 flex-shrink-0">
        <div className={`w-1.5 h-1.5 rounded-full ${STATUS_COLORS[status]}`} />
        <span className="text-[9px] font-bold text-gray-600 uppercase tracking-widest">Terminal Output</span>
        <span className="ml-auto text-[9px] text-gray-700 font-mono">{strategyName} · {status}</span>
      </div>
      {/* Output */}
      <div className="flex-1 overflow-y-auto px-3.5 py-2 font-mono text-[10px] leading-relaxed space-y-0.5">
        {lines.map((l, i) => (
          <div key={i} className={TYPE_CLASSES[l.type]}>{l.text}</div>
        ))}
        {(status === 'running' || status === 'ready') && (
          <div>
            <span className="inline-block w-1.5 h-3 bg-green-500 align-text-bottom animate-pulse" />
          </div>
        )}
      </div>
    </div>
  );
}
