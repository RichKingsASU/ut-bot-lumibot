import type { Handler } from '@netlify/functions'

const handler: Handler = async (event) => {
  const dataUrl = process.env.ALPACA_DATA_URL || 'https://data.alpaca.markets'
  const apiKey = process.env.ALPACA_API_KEY || ''
  const apiSecret = process.env.ALPACA_API_SECRET || ''

  const params = event.queryStringParameters || {}
  const symbol = params.symbol || 'IWM'
  const timeframe = params.timeframe || '15Min'
  const limit = params.limit || '200'

  // Map simple timeframe codes to Alpaca API format
  const tfMap: Record<string, string> = {
    '1m': '1Min', '5m': '5Min', '15m': '15Min',
    '1h': '1Hour', '1D': '1Day',
  }
  const alpacaTf = tfMap[timeframe] || timeframe

  try {
    const url = `${dataUrl}/v2/stocks/${encodeURIComponent(symbol)}/bars?timeframe=${alpacaTf}&limit=${limit}&feed=iex&adjustment=raw`
    const response = await fetch(url, {
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

    const data = await response.json() as { bars: Array<{ t: string; o: number; h: number; l: number; c: number; v: number }> }
    
    // Normalize to simple array
    const bars = (data.bars || []).map((b) => ({
      t: b.t,
      o: b.o,
      h: b.h,
      l: b.l,
      c: b.c,
      v: b.v,
    }))

    return {
      statusCode: 200,
      body: JSON.stringify({ bars }),
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
