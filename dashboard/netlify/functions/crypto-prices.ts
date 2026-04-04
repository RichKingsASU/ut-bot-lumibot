import type { Handler } from '@netlify/functions'

const handler: Handler = async (event) => {
  const apiKey = process.env.ALPACA_API_KEY || ''
  const apiSecret = process.env.ALPACA_API_SECRET || ''
  const symbols = (event.queryStringParameters?.symbols || 'BTC/USD,ETH/USD,SOL/USD,AVAX/USD')
    .split(',')

  try {
    const encoded = symbols.map(s => encodeURIComponent(s)).join(',')
    const res = await fetch(
      `https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes?symbols=${encoded}`,
      {
        headers: {
          'APCA-API-KEY-ID': apiKey,
          'APCA-API-SECRET-KEY': apiSecret,
        },
      }
    )

    if (!res.ok) {
      const text = await res.text()
      return {
        statusCode: res.status,
        body: JSON.stringify({ error: text }),
        headers: { 'Content-Type': 'application/json' },
      }
    }

    const data = await res.json()
    return {
      statusCode: 200,
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=15',
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
