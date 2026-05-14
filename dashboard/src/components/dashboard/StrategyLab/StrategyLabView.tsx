import { useState, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { StrategyLibrary, LabStrategy } from './StrategyLibrary';
import { CodeEditor } from './CodeEditor';
import { TerminalPanel, TerminalLine } from './TerminalPanel';
import { BacktestPanel } from './BacktestPanel';
import { supabase } from '../../../lib/supabaseClient';
import { PageHeader } from '../../ui/PageHeader';
import { Maximize2, Minimize2, Terminal, Code2, PlayCircle, Settings } from 'lucide-react';

const DEFAULT_STRATEGIES: LabStrategy[] = [
  {
    id: 'ut-bot-v2',
    name: 'UT Bot Scalper V2',
    filename: 'ut_bot_scalper_v2.py',
    language: 'Python',
    status: 'active',
    lastSaved: 'Last saved 2m ago',
    code: `# ut_bot_scalper_v2.py — UT Bot ATR Trailing Stop\n# Lumibot v4.4.61 · Alpaca paper trading\n\nfrom lumibot.strategies import Strategy\nfrom lumibot.entities import Asset\nimport pandas as pd\nimport numpy as np\n\nclass UTBotScalper(Strategy):\n    parameters = {\n        "atr_period": 14,\n        "sensitivity": 2.0,\n        "symbol": "IWM",\n        "timeframe": "15m",\n    }\n\n    def initialize(self):\n        self.sleeptime = "15M"\n        self.atr_period = self.parameters["atr_period"]\n        self.sensitivity = self.parameters["sensitivity"]\n\n    def on_trading_iteration(self):\n        symbol = self.parameters["symbol"]\n        bars = self.get_historical_prices(\n            symbol, self.atr_period + 2, "minute"\n        )\n        df = bars.df\n        atr = self._compute_atr(df)\n        stop = df["close"].iloc[-1] - self.sensitivity * atr\n\n        if df["close"].iloc[-1] > stop:\n            self.buy(symbol, quantity=1)\n        else:\n            self.sell_all()\n\n    def _compute_atr(self, df):\n        h = df["high"]; l = df["low"]; c = df["close"]\n        tr = pd.concat([h - l, (h - c.shift()).abs(),\n                        (l - c.shift()).abs()], axis=1).max(axis=1)\n        return tr.ewm(span=self.atr_period).mean().iloc[-1]\n`,
    backtestResult: {
      totalReturn: '+12.4%', sharpe: '1.84', winRate: '68%',
      maxDrawdown: '-3.2%', vol: 'Vol: 0.8%', version: 'V2.0',
      curve: '0,48 30,42 60,36 90,40 120,28 150,22 180,16 200,12',
    },
  },
  {
    id: 'ema-crossover',
    name: 'EMA Crossover',
    filename: 'ema_crossover.py',
    language: 'Python',
    status: 'draft',
    lastSaved: 'Unsaved',
    code: `# ema_crossover.py — Dual EMA Crossover with volume confirmation\n\nfrom lumibot.strategies import Strategy\nimport pandas as pd\n\nclass EMACrossover(Strategy):\n    parameters = {\n        "fast_period": 20,\n        "slow_period": 50,\n        "symbol": "SPY",\n    }\n\n    def initialize(self):\n        self.sleeptime = "15M"\n\n    def on_trading_iteration(self):\n        symbol = self.parameters["symbol"]\n        bars = self.get_historical_prices(symbol, 60, "minute")\n        df = bars.df\n        fast_ema = df["close"].ewm(span=self.parameters["fast_period"]).mean()\n        slow_ema = df["close"].ewm(span=self.parameters["slow_period"]).mean()\n\n        if fast_ema.iloc[-1] > slow_ema.iloc[-1]:\n            self.buy(symbol, quantity=1)\n        elif fast_ema.iloc[-1] < slow_ema.iloc[-1]:\n            self.sell_all()\n`,
  }
];

const StrategyLabView: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [strategies, setStrategies] = useState<LabStrategy[]>(DEFAULT_STRATEGIES);
  const [selectedId, setSelectedId] = useState('ut-bot-v2');
  const [terminalLines, setTerminalLines] = useState<TerminalLine[]>([
    { type: 'dim', text: '[system] Strategy Lab v2.0 Initialization sequence complete.' },
    { type: 'info', text: '[ready] Listening on dev-container-01' },
  ]);
  const [terminalStatus, setTerminalStatus] = useState<'ready'|'running'|'done'|'error'>('ready');
  const [lastSaved, setLastSaved] = useState('Last saved 2m ago');
  const [backtestResult, setBacktestResult] = useState<LabStrategy['backtestResult'] | null>(
    DEFAULT_STRATEGIES[0].backtestResult || null
  );
  const [cpuPct, setCpuPct] = useState(14);
  const [deployTarget, setDeployTarget] = useState<'equities' | 'crypto'>('equities');
  const [deploySymbol, setDeploySymbol] = useState('IWM');
  const [isTerminalCollapsed, setIsTerminalCollapsed] = useState(false);

  const selected = strategies.find(s => s.id === selectedId) || strategies[0];

  const handleRunBacktest = useCallback((params: any) => {
    setTerminalStatus('running');
    setTerminalLines(prev => [...prev, { type: 'info', text: `[backtest] Initializing simulation for ${params.symbol}...` }]);
    
    // Simulating progress
    setTimeout(() => {
        setTerminalLines(prev => [...prev, { type: 'ok', text: '[backtest] Simulation complete. Analyzing results...' }]);
        setBacktestResult(selected.backtestResult || {
            totalReturn: '+8.2%', sharpe: '1.41', winRate: '62%',
            maxDrawdown: '-4.8%', vol: 'Vol: 1.2%', version: 'V2.1', curve: '0,46 40,40 80,34 120,37 160,24 200,17'
        });
        setTerminalStatus('done');
    }, 2000);
  }, [selected]);

  return (
    <div className="flex flex-col h-full bg-space text-primary overflow-hidden">
      {/* Dynamic Header */}
      <div className="p-4 bg-surface-1/50 border-b border-border-muted backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center justify-between">
            <PageHeader 
                title="Strategy Lab" 
                subtitle={
                    <div className="flex items-center gap-2">
                        <span className="p-1 bg-surface-2 rounded border border-border-muted text-[10px] font-mono text-secondary">
                            {selected.filename}
                        </span>
                        <span className="text-[10px] text-dim">{lastSaved}</span>
                    </div>
                } 
            />
            <div className="flex items-center gap-2">
                <button className="p-2 hover:bg-surface-2 rounded-lg transition-smooth text-secondary hover:text-vibrant">
                    <Maximize2 className="w-4 h-4" />
                </button>
                <button className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-xs font-bold text-white transition-smooth shadow-lg shadow-blue-900/20 flex items-center gap-2">
                    <PlayCircle className="w-4 h-4" />
                    Deploy System
                </button>
            </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* SIDEBAR: Library */}
        <aside className="w-64 border-r border-border-muted flex-shrink-0 z-10 shadow-xl">
          <StrategyLibrary
            strategies={strategies}
            selectedId={selectedId}
            onSelect={(s) => setSelectedId(s.id)}
            onUpload={(code, filename) => {}}
          />
        </aside>

        {/* MAIN: Editor & Terminal */}
        <main className="flex-1 flex flex-col min-w-0 bg-surface-0 relative">
          {/* View Toggle (Floating) */}
          <div className="absolute top-4 right-4 z-10 flex gap-1 p-1 bg-surface-2/80 backdrop-blur border border-border-muted rounded-full">
            <button className="px-3 py-1.5 rounded-full text-[10px] font-bold bg-blue-500 text-white shadow-sm">Code</button>
            <button className="px-3 py-1.5 rounded-full text-[10px] font-bold text-secondary hover:text-vibrant">Visual</button>
          </div>

          <div className="flex-1 overflow-hidden p-2">
            <div className="h-full rounded-2xl border border-border-muted overflow-hidden shadow-2xl">
                <CodeEditor
                    filename={selected.filename}
                    code={selected.code}
                    lastSaved={lastSaved}
                    onCompile={() => {}}
                    onBacktest={() => {}}
                    onSave={() => {}}
                />
            </div>
          </div>

          {/* Terminal Panel */}
          <motion.div 
            animate={{ height: isTerminalCollapsed ? 44 : 200 }}
            className="border-t border-border-muted bg-surface-1 flex flex-col flex-shrink-0 transition-all duration-300"
          >
            <div className="px-4 py-3 flex items-center justify-between border-b border-border-muted/50 cursor-pointer" onClick={() => setIsTerminalCollapsed(!isTerminalCollapsed)}>
                <div className="flex items-center gap-2">
                    <Terminal className="w-3.5 h-3.5 text-blue-400" />
                    <span className="text-[10px] font-bold text-secondary uppercase tracking-widest">Process Terminal</span>
                    {terminalStatus === 'running' && (
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping ml-1" />
                    )}
                </div>
                <button className="text-dim hover:text-secondary">
                    {isTerminalCollapsed ? <Maximize2 className="w-3.5 h-3.5" /> : <Minimize2 className="w-3.5 h-3.5" />}
                </button>
            </div>
            <div className="flex-1 overflow-hidden p-2">
                <div className="h-full bg-space/50 rounded-xl border border-border-muted/30">
                    <TerminalPanel
                        lines={terminalLines}
                        status={terminalStatus}
                        strategyName={selected.filename}
                    />
                </div>
            </div>
          </motion.div>
        </main>

        {/* CONTROLS: Backtest & AI */}
        <aside className="w-80 border-l border-border-muted flex-shrink-0 z-10 shadow-xl overflow-hidden">
          <BacktestPanel
            result={backtestResult}
            cpuPct={cpuPct}
            onRunBacktest={handleRunBacktest}
            deployTarget={deployTarget}
            deploySymbol={deploySymbol}
            onSetTarget={setDeployTarget}
            onSetSymbol={setDeploySymbol}
            onDeploy={() => {}}
          />
        </aside>
      </div>
    </div>
  );
}

export default StrategyLabView;
