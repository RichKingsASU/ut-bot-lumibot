import type { Handler } from '@netlify/functions'
import { requireAdmin, isAllowedAlpacaBaseUrl, ALPACA_PAPER_URL } from "./lib/auth"

const handler: Handler = async (event) => {
  // Require admin auth for ALL callers, including those supplying credentials
  // in the body (DA-03): this proxy must not be an open credential/base-URL
  // relay. Fails closed when ADMIN_API_KEY is unset in a deployed context.
  const auth = requireAdmin(event);
  if (!auth.ok) {
    return { statusCode: auth.statusCode, body: auth.body };
  }

  let apiKey = process.env.ALPACA_API_KEY || ''
  let apiSecret = process.env.ALPACA_API_SECRET || ''
  let baseUrl = process.env.ALPACA_BASE_URL || ALPACA_PAPER_URL

  // Allow overriding for testing (Settings → Test Connection sends user-typed creds)
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

  // Whitelist the base URL (DA-03): never let a caller-supplied value point
  // this proxy at an arbitrary host.
  if (!isAllowedAlpacaBaseUrl(baseUrl)) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: "Invalid baseUrl. Must be an Alpaca REST endpoint." }),
    };
  }

  console.log('[alpaca-account] key present:', !!process.env.ALPACA_API_KEY)
  console.log('[alpaca-account] secret present:', !!process.env.ALPACA_API_SECRET)
  console.log('[alpaca-account] base url:', baseUrl)

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
