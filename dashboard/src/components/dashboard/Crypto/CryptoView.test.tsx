import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CryptoView } from './CryptoView'

// Mock Supabase client
vi.mock('../../../lib/supabaseClient', () => ({
  supabase: {
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        in: vi.fn(() => ({
          order: vi.fn(() => ({
            limit: vi.fn(() => Promise.resolve({
              data: [
                { id: '1', symbol: 'BTC/USD', action: 'BUY', confidence: 0.92, created_at: '2026-07-09T02:00:00Z' }
              ],
              error: null
            }))
          }))
        })),
        eq: vi.fn(() => ({
          order: vi.fn(() => ({
            limit: vi.fn(() => Promise.resolve({
              data: [
                { id: '1', symbol: 'BTC/USD', action: 'BUY', confidence: 0.92, created_at: '2026-07-09T02:00:00Z' }
              ],
              error: null
            }))
          }))
        }))
      }))
    }))
  }
}))

describe('CryptoView Component', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          quotes: {
            'BTC/USD': { price: 65200.50, change_pct: 1.25, ap: 65201, bp: 65200 },
            'ETH/USD': { price: 3450.75, change_pct: -0.5, ap: 3451, bp: 3450 },
            'SOL/USD': { price: 145.20, change_pct: 4.8, ap: 145.3, bp: 145.1 }
          }
        })
      })
    ))
  })

  it('renders Crypto Monitoring panel and loads mock asset prices', async () => {
    render(<CryptoView />)

    // Check if the title is loaded
    expect(screen.getByText('Crypto Surveillance')).toBeInTheDocument()

    // Wait for the mock fetch call to complete and assert price displays
    await waitFor(() => {
      expect(screen.getByText('$65,200.50')).toBeInTheDocument()
      expect(screen.getByText('$3,450.75')).toBeInTheDocument()
      expect(screen.getByText('$145.20')).toBeInTheDocument()
    })
  })
})
