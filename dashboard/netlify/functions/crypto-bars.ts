import type { Handler } from '@netlify/functions'

const handler: Handler = async (event) => {
  const apiKey = process.env.ALPACA_API_KEY || ''
  const apiSecret = process.env.ALPACA_API_SECRET || ''
  const symbol = event.queryStringParameters?.symbol || 'BTC/USD'
  const timeframe = event.queryStringParameters?.timeframe || '1Min'
  const limit = event.queryStringParameters?.limit || '200'

  try {
    const encoded = encodeURIComponent(symbol)
    // Use start=24h-ago + sort=asc so we always pull recent bars (which have
    // real trade volume) instead of the oldest available bars from when the
    // crypto feed first started indexing — those can come back with v=0.
    const start = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
    const url =
      `https://data.alpaca.markets/v1beta3/crypto/us/bars` +
      `?symbols=${encoded}` +
      `&timeframe=${timeframe}` +
      `&limit=${limit}` +
      `&start=${encodeURIComponent(start)}` +
      `&sort=desc`

    const res = await fetch(url, {
      headers: {
        'APCA-API-KEY-ID': apiKey,
        'APCA-API-SECRET-KEY': apiSecret,
      },
    })

    if (!res.ok) {
      const text = await res.text()
      return {
        statusCode: res.status,
        body: JSON.stringify({ error: text }),
        headers: { 'Content-Type': 'application/json' },
      }
    }

    // Alpaca v1beta3 crypto bar fields:
    //   t  ISO timestamp
    //   o,h,l,c  prices
    //   v  volume in BASE currency (e.g. BTC)  ← real trade volume
    //   vw volume-weighted average price
    //   n  trade count
    // Normalize each bar so the frontend can rely on bar.v being a number,
    // and reverse to chronological order for charting.
    const data = (await res.json()) as { bars?: Record<string, any[]>; next_page_token?: string | null }
    const symBars = (data.bars && data.bars[symbol]) || []
    const normalizedBars = symBars
      .map((b: any) => ({
        t: b.t,
        o: Number(b.o ?? 0),
        h: Number(b.h ?? 0),
        l: Number(b.l ?? 0),
        c: Number(b.c ?? 0),
        v: Number(b.v ?? 0),
        vw: Number(b.vw ?? 0),
        n: Number(b.n ?? 0),
      }))
      .reverse()

    return {
      statusCode: 200,
      body: JSON.stringify({
        bars: { [symbol]: normalizedBars },
        next_page_token: data.next_page_token ?? null,
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
