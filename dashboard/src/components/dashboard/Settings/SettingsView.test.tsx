import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { SettingsView } from './SettingsView'

// Shared, hoisted mock state so the vi.mock factory can reference it.
const { upsertCalls, store } = vi.hoisted(() => ({
  upsertCalls: [] as Array<{ values: any; opts: any }>,
  // paper_mode persisted as LIVE — proves the toggle loads from Supabase, not
  // from the React default (which is paper).
  store: {
    paper_mode: { value: { paper_mode: false, base_url: 'https://api.alpaca.markets' } },
    telegram_config: { value: JSON.stringify({ token: 'tok', chatId: 'chat' }) },
    broker_credentials: { value: { api_key: 'PKLIVE1234567890', api_secret: 'shhh-secret' } },
  } as Record<string, any>,
}))

vi.mock('../../../lib/supabaseClient', () => ({
  supabase: {
    from: () => {
      let capturedKey: string | null = null
      const builder: any = {
        select: () => builder,
        eq: (_col: string, val: string) => {
          capturedKey = val
          return builder
        },
        maybeSingle: () =>
          Promise.resolve({ data: capturedKey ? store[capturedKey] ?? null : null, error: null }),
        upsert: (values: any, opts: any) => {
          upsertCalls.push({ values, opts })
          return Promise.resolve({ data: null, error: null })
        },
      }
      return builder
    },
  },
}))

vi.mock('../../ui/PageHeader', () => ({
  PageHeader: ({ title }: { title: string }) => <div>{title}</div>,
}))

describe('SettingsView — Broker Configuration wiring', () => {
  beforeEach(() => {
    upsertCalls.length = 0
  })

  it('loads the trading mode from Supabase so the toggle survives a refresh', async () => {
    render(<SettingsView />)
    // Persisted value is LIVE; the default React state is paper. If loading
    // works, "Live Mode" appears.
    expect(await screen.findByText('Live Mode')).toBeInTheDocument()
  })

  it('masks stored broker credentials on reload (never shows the full key)', async () => {
    render(<SettingsView />)
    const keyInput = await screen.findByPlaceholderText(/Stored: PK/)
    expect(keyInput.getAttribute('placeholder')).toContain('PK')
    // The full key must never appear anywhere in the DOM.
    expect(screen.queryByDisplayValue('PKLIVE1234567890')).toBeNull()
    expect(document.body.innerHTML).not.toContain('PKLIVE1234567890')
    expect(document.body.innerHTML).not.toContain('shhh-secret')
  })

  it('saves Telegram config as an upsert with onConflict:key (fixes the 409)', async () => {
    render(<SettingsView />)
    await screen.findByText('Live Mode') // wait for effects to settle
    fireEvent.click(screen.getByText('Save Telegram Config'))

    await waitFor(() => {
      const call = upsertCalls.find((c) => c.values.key === 'telegram_config')
      expect(call).toBeTruthy()
      expect(call?.opts?.onConflict).toBe('key')
    })
    expect(await screen.findByText('Telegram config saved.')).toBeInTheDocument()
  })

  it('saves the broker/trading mode as an upsert with onConflict:key; blank creds = unchanged', async () => {
    render(<SettingsView />)
    await screen.findByText('Live Mode')
    // Leave key/secret blank — stored values exist, so this is a valid save.
    fireEvent.click(screen.getByText('Save Broker Config'))

    await waitFor(() => {
      const call = upsertCalls.find((c) => c.values.key === 'paper_mode')
      expect(call).toBeTruthy()
      expect(call?.opts?.onConflict).toBe('key')
      // No required-field error, and no accidental credential overwrite.
      expect(upsertCalls.find((c) => c.values.key === 'broker_credentials')).toBeFalsy()
    })
  })
})
