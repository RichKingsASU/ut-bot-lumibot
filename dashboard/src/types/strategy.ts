export interface Strategy {
  id: string
  name: string
  description: string
  symbol: string
  timeframe: string
  status: 'active' | 'paused' | 'stopped' | 'draft'
  mode: 'paper' | 'live'
  parameters: Record<string, number | string | boolean>
  created_at: string
  updated_at: string
  performance?: {
    total_return: number
    win_rate: number
    sharpe_ratio: number
    max_drawdown: number
    total_trades: number
  }
}

export interface BacktestResult {
  id: string
  strategy_id: string
  start_date: string
  end_date: string
  initial_balance: number
  final_balance: number
  total_return: number
  sharpe_ratio: number
  max_drawdown: number
  win_rate: number
  total_trades: number
  trades: BacktestTrade[]
  equity_curve: { time: string; value: number }[]
  status: 'running' | 'completed' | 'failed'
  progress: number
}

export interface BacktestTrade {
  entry_time: string
  exit_time: string
  symbol: string
  side: 'long' | 'short'
  entry_price: number
  exit_price: number
  quantity: number
  pnl: number
  return_pct: number
}
