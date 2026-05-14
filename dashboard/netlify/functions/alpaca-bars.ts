import type { Handler } from '@netlify/functions'
import { logAlert } from "./lib/alerts"

// Simple in-memory cooldown for serverless environment (per execution context)
const lastRequestTime = new Map<string, number>();
const COOLDOWN_MS = 1000; // 1s

const handler: Handler = async (event) => {
  // ── [SECURITY FIX] Admin Auth ──────────────────────────────────────
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = event.headers['x-admin-api-key'];
  if (adminKey && requestKey !== adminKey) {
    return { statusCode: 401, body: JSON.stringify({ error: "Unauthorized" }) };
  }

  const clientIp = event.headers['client-ip'] || 'unknown';
  const now = Date.now();
  if (lastRequestTime.has(clientIp) && (now - lastRequestTime.get(clientIp)!) < COOLDOWN_MS) {
    return { statusCode: 429, body: JSON.stringify({ error: "Too Many Requests" }) };
  }
  lastRequestTime.set(clientIp, now);

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
      if (response.status === 401) {
        await logAlert(
          "Alpaca API Authentication Failed (401). Please check your ALPACA_API_KEY and SECRET.",
          "CRITICAL",
          "SECURITY"
        );
      }
      return {
        statusCode: response.status,
        body: JSON.stringify({ error: "Failed to fetch bars from Alpaca" }),
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
    console.error("[alpaca-bars] Error:", err);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: "Internal Server Error" }),
      headers: { 'Content-Type': 'application/json' },
    }
  }
}

export { handler }
