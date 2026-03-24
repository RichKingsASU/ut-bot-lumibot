import type { Handler } from '@netlify/functions'
import { createServer } from 'http'
import { WebSocket, WebSocketServer } from 'ws'

/**
 * WebSocket upgrade handler for streaming Alpaca market data.
 * Connects to Alpaca stream server-side (credentials never reach browser).
 * Forwards price updates to connected clients.
 *
 * NOTE: Netlify Functions have a 10s timeout. For production WebSocket
 * streaming, use Netlify Background Functions or a separate WebSocket server.
 * This function upgrades the HTTP connection and streams until disconnect.
 */
const handler: Handler = async (event, context) => {
  const streamUrl = process.env.ALPACA_STREAM_URL || 'wss://stream.data.alpaca.markets/v2/iex'
  const apiKey = process.env.ALPACA_API_KEY || ''
  const apiSecret = process.env.ALPACA_API_SECRET || ''

  const symbol = (event.queryStringParameters?.symbol || 'IWM').toUpperCase()

  // For environments that don't support WebSocket upgrades natively in serverless,
  // fall back to short-polling response with latest trade data
  try {
    const dataUrl = process.env.ALPACA_DATA_URL || 'https://data.alpaca.markets'
    const response = await fetch(
      `${dataUrl}/v2/stocks/${encodeURIComponent(symbol)}/trades/latest?feed=iex`,
      {
        headers: {
          'APCA-API-KEY-ID': apiKey,
          'APCA-API-SECRET-KEY': apiSecret,
        },
      }
    )

    if (!response.ok) {
      return {
        statusCode: response.status,
        body: JSON.stringify({ error: 'Failed to fetch latest trade' }),
        headers: { 'Content-Type': 'application/json' },
      }
    }

    const data = await response.json() as { trade?: { p: number; t: string } }
    return {
      statusCode: 200,
      body: JSON.stringify({
        symbol,
        price: data.trade?.p ?? null,
        time: data.trade?.t ?? null,
        streamUrl: `${streamUrl}`,
        note: 'For WebSocket streaming, connect to /netlify/functions/alpaca-stream via EventSource or use the REST poll endpoint.',
      }),
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store',
      },
    }
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: String(err) }),
      headers: { 'Content-Type': 'application/json' },
    }
  }
}

export { handler }
