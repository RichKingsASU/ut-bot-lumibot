import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import OverviewView from './OverviewView'

// Mock react-router-dom Link
vi.mock('react-router-dom', () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  )
}))

// Mock ResponsiveContainer for Recharts compatibility in tests
vi.mock('recharts', async () => {
  const original = await vi.importActual('recharts')
  return {
    ...original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div>{children}</div>
    )
  }
})

// Mock useTradingContext hook
vi.mock('../../../context/TradingContext', () => ({
  useTradingContext: () => ({
    tradingMode: 'paper',
    isHealthy: true,
    lastHeartbeat: '2026-07-09T02:00:00Z',
    setTradingMode: vi.fn(),
    account: { equity: 100000, cash: 50000 },
    positions: [{ symbol: 'BTCUSD' }, { symbol: 'ETHUSD' }],
    signals: [],
    logs: [],
    connected: true,
    botStatus: { status: 'running' },
    loading: false
  })
}))

// Mock useMetrics hook
vi.mock('../../../hooks/useMetrics', () => ({
  useMetrics: () => ({
    winRate: 65,
    totalTrades: 120,
    totalPnl: 5400.00,
    maxDrawdown: -4.50,
    openPositions: 2,
    loading: false,
    error: null,
  })
}))

// Mock Supabase client queries
vi.mock('../../../lib/supabaseClient', () => ({
  supabase: {
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        order: vi.fn(() => ({
          limit: vi.fn(() => ({
            maybeSingle: vi.fn(() => Promise.resolve({ data: { regime: 'BULL', probability: 0.95, detected_at: '2026-07-09T02:00:00Z' }, error: null })),
            then: vi.fn((resolve) => resolve({ data: [], error: null }))
          })),
          then: vi.fn((resolve) => resolve({ data: [], error: null }))
        }))
      }))
    }))
  }
}))

describe('OverviewView Component', () => {
  it('renders overview header and statistics metrics correctly', async () => {
    render(<OverviewView />)

    // Check if key metrics are displayed on the cards
    expect(screen.getByText('$100,000.00')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('65%')).toBeInTheDocument()
  })
})
