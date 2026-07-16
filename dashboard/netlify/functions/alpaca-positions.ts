import type { Handler } from '@netlify/functions'
import { requireAdmin, ALPACA_PAPER_URL } from "./lib/auth"

const handler: Handler = async (event) => {
  // Fail-CLOSED admin auth (DA-06).
  const auth = requireAdmin(event);
  if (!auth.ok) {
    return { statusCode: auth.statusCode, body: auth.body };
  }

  const baseUrl = process.env.ALPACA_BASE_URL || ALPACA_PAPER_URL
  const apiKey = process.env.ALPACA_API_KEY || ''
  const apiSecret = process.env.ALPACA_API_SECRET || ''

  try {
    const response = await fetch(`${baseUrl}/v2/positions`, {
      headers: {
        'APCA-API-KEY-ID': apiKey,
        'APCA-API-SECRET-KEY': apiSecret,
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      const text = await response.text()
      return {
        statusCode: response.status,
        body: JSON.stringify({ error: text }),
        headers: { 'Content-Type': 'application/json' },
      }
    }

    const data = await response.json()
    return {
      statusCode: 200,
      body: JSON.stringify(data),
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
