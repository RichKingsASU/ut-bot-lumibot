import type { Handler } from '@netlify/functions'

const handler: Handler = async (event) => {
  // ── [SECURITY FIX] Admin Auth ──────────────────────────────────────
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = event.headers['x-admin-api-key'];
  if (adminKey && requestKey !== adminKey) {
    return { statusCode: 401, body: JSON.stringify({ error: "Unauthorized" }) };
  }

  let apiKey = process.env.ALPACA_API_KEY || ''
  let apiSecret = process.env.ALPACA_API_SECRET || ''
  let baseUrl = process.env.ALPACA_BASE_URL || 'https://paper-api.alpaca.markets'

  // Allow overriding for testing
  if (event.httpMethod === 'POST' && event.body) {
    try {
      const body = JSON.parse(event.body);
      if (body.apiKey) apiKey = body.apiKey;
      if (body.apiSecret) apiSecret = body.apiSecret;
      if (body.baseUrl) baseUrl = body.baseUrl;
    } catch (e) {
      return { statusCode: 400, body: JSON.stringify({ error: "Invalid JSON" }) };
    }
  }

  const startTime = Date.now();
  try {
    const response = await fetch(`${baseUrl}/v2/account`, {
      headers: {
        'APCA-API-KEY-ID': apiKey,
        'APCA-API-SECRET-KEY': apiSecret,
        'Content-Type': 'application/json',
      },
    })

    const latency = Date.now() - startTime;

    if (!response.ok) {
      const text = await response.text()
      let errorMessage = text;
      try {
        const errJson = JSON.parse(text);
        errorMessage = errJson.message || text;
      } catch (e) { /* ignore */ }

      return {
        statusCode: response.status,
        body: JSON.stringify({ 
          error: errorMessage,
          statusCode: response.status,
          latency 
        }),
        headers: { 'Content-Type': 'application/json' },
      }
    }

    const data = await response.json()
    return {
      statusCode: 200,
      body: JSON.stringify({
        ...data,
        latency,
        isPaper: baseUrl.includes('paper-api'),
        baseUrl
      }),
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store',
      },
    }
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: String(err), latency: Date.now() - startTime }),
      headers: { 'Content-Type': 'application/json' },
    }
  }
}

export { handler }
