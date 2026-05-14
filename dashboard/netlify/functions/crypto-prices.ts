import type { Handler } from '@netlify/functions'

const handler: Handler = async (event) => {
  // ── [SECURITY FIX] Admin Auth ──────────────────────────────────────
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = event.headers['x-admin-api-key'];
  if (adminKey && requestKey !== adminKey) {
    return { statusCode: 401, body: JSON.stringify({ error: "Unauthorized" }) };
  }

  const apiKey = process.env.ALPACA_API_KEY || ''
  const apiSecret = process.env.ALPACA_API_SECRET || ''
  const symbols = (event.queryStringParameters?.symbols || 'BTC/USD,ETH/USD,SOL/USD,AVAX/USD')
    .split(',')

  try {
    const encoded = symbols.map(s => encodeURIComponent(s)).join(',')

    // Use /snapshots so we can compute a real 24h change from prevDailyBar.c.
    // The /latest/quotes endpoint only returns bid/ask which has no daily
    // reference price, forcing the frontend to fall back to 0% change.
    const res = await fetch(
      `https://data.alpaca.markets/v1beta3/crypto/us/snapshots?symbols=${encoded}`,
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

    type Snapshot = {
      latestTrade?: { p?: number }
      latestQuote?: { ap?: number; bp?: number }
      dailyBar?:    { o?: number; h?: number; l?: number; c?: number; v?: number }
      prevDailyBar?:{ o?: number; h?: number; l?: number; c?: number; v?: number }
      minuteBar?:   { o?: number; h?: number; l?: number; c?: number; v?: number }
    }

    const data = (await res.json()) as { snapshots?: Record<string, Snapshot> }
    const snapshots = data.snapshots || {}

    // Build a unified per-symbol payload the frontend can render directly:
    //   { symbol, price, change_pct, ap, bp }
    // change_pct = ((dailyBar.c - prevDailyBar.c) / prevDailyBar.c) * 100
    const quotes: Record<string, {
      symbol: string
      price: number
      change_pct: number
      ap: number
      bp: number
    }> = {}

    for (const sym of symbols) {
      const snap = snapshots[sym] || {}
      const price =
        snap.dailyBar?.c ??
        snap.minuteBar?.c ??
        snap.latestTrade?.p ??
        ((snap.latestQuote?.ap ?? 0) + (snap.latestQuote?.bp ?? 0)) / 2 ??
        0
      const prevClose = snap.prevDailyBar?.c
      const dayClose = snap.dailyBar?.c
      const changePct =
        prevClose && dayClose && prevClose > 0
          ? ((dayClose - prevClose) / prevClose) * 100
          : 0

      quotes[sym] = {
        symbol: sym,
        price: Number(price) || 0,
        change_pct: Number(changePct) || 0,
        ap: Number(snap.latestQuote?.ap ?? 0),
        bp: Number(snap.latestQuote?.bp ?? 0),
      }
    }

    return {
      statusCode: 200,
      body: JSON.stringify({ quotes }),
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
