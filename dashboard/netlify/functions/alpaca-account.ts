import type { Handler } from '@netlify/functions'

const handler: Handler = async () => {
  const baseUrl = process.env.ALPACA_BASE_URL || 'https://paper-api.alpaca.markets'
  const apiKey = process.env.ALPACA_API_KEY || ''
  const apiSecret = process.env.ALPACA_API_SECRET || ''

  try {
    const response = await fetch(`${baseUrl}/v2/account`, {
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
