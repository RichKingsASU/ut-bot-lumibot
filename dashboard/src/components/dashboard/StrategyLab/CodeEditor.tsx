interface Props {
  filename: string;
  code: string;
  lastSaved: string;
  onCompile: () => void;
  onBacktest: () => void;
  onSave: () => void;
}

// Minimal tokeniser for Python syntax highlighting
function highlight(code: string): string {
  const keywords = ['import','from','class','def','if','elif','else','return',
    'for','while','in','and','or','not','True','False','None','self','as'];
  let html = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // comments
  html = html.replace(/(#[^\n]*)/g, '<span class="text-gray-600 italic">$1</span>');
  // strings
  html = html.replace(/("""[\s\S]*?"""|'''[\s\S]*?'''|"[^"]*"|'[^']*')/g,
    '<span class="text-yellow-300">$1</span>');
  // numbers
  html = html.replace(/\b(\d+\.?\d*)\b/g, '<span class="text-orange-400">$1</span>');
  // keywords
  keywords.forEach(kw => {
    html = html.replace(new RegExp(`\\b(${kw})\\b`, 'g'),
      '<span class="text-indigo-400">$1</span>');
  });
  // function/class names
  html = html.replace(/\b(def|class)\s+([A-Za-z_]\w*)/g,
    '$1 <span class="text-emerald-400">$2</span>');
  // method calls
  html = html.replace(/\.([a-z_]\w*)\(/g, '.<span class="text-emerald-400">$1</span>(');

  return html;
}

export function CodeEditor({ filename, code, lastSaved, onCompile, onBacktest, onSave }: Props) {
  const lines = code.split('\n');

  return (
    <div className="flex flex-col h-full bg-black">
      {/* Toolbar */}
      <div className="flex items-center px-3 h-9 bg-[#0d0f1a] border-b border-gray-800 flex-shrink-0 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
          <span className="text-xs font-semibold text-gray-300 font-mono truncate">{filename}</span>
          <span className="text-[10px] text-gray-700 flex-shrink-0">{lastSaved}</span>
        </div>
        <div className="ml-auto flex gap-1.5">
          <button
            onClick={onCompile}
            className="flex items-center gap-1 px-2.5 py-1 bg-[#0d0f1a] border border-gray-800 rounded text-[10px] font-semibold text-gray-400 hover:border-gray-600 hover:text-gray-200 transition-colors"
          >
            <svg className="w-2.5 h-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="1" y="1" width="8" height="8" rx="1"/>
              <polyline points="3,3 5,5 3,7"/>
            </svg>
            Compile
          </button>
          <button
            onClick={onBacktest}
            className="flex items-center gap-1 px-2.5 py-1 bg-blue-950 border border-blue-900 rounded text-[10px] font-semibold text-blue-400 hover:bg-blue-900 transition-colors"
          >
            <svg className="w-2.5 h-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <polyline points="2,1.5 8,5 2,8.5"/>
            </svg>
            Backtest
          </button>
          <button
            onClick={onSave}
            className="flex items-center gap-1 px-2.5 py-1 bg-green-950 border border-green-900 rounded text-[10px] font-semibold text-green-400 hover:bg-green-900 transition-colors"
          >
            <svg className="w-2.5 h-2.5" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M1.5 1.5h5.5l1.5 1.5v6H1.5z"/>
              <rect x="3" y="6" width="3" height="3"/>
              <rect x="3" y="1.5" width="2.5" height="2"/>
            </svg>
            Save
          </button>
        </div>
      </div>

      {/* Code area */}
      <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed">
        <div className="flex gap-4">
          {/* Line numbers */}
          <div className="select-none text-right text-gray-700 pr-3 border-r border-gray-900 flex-shrink-0" style={{ minWidth: '28px' }}>
            {lines.map((_, i) => (
              <div key={i} className="text-[10.5px] leading-[1.75]">{i + 1}</div>
            ))}
          </div>
          {/* Code with syntax highlighting */}
          <div className="flex-1 whitespace-pre leading-[1.75] text-gray-400 text-[11.5px]">
            {lines.map((line, i) => (
              <div
                key={i}
                dangerouslySetInnerHTML={{ __html: highlight(line) || '&nbsp;' }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
