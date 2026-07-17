import type { Handler } from '@netlify/functions'
import {
  requireAdmin,
  isAllowedAlpacaBaseUrl,
  ALPACA_PAPER_URL,
  ERROR_SOURCE,
  ERROR_CODE,
} from "./lib/auth"

const JSON_HEADER = { 'Content-Type': 'application/json' }

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
      return {
        statusCode: 400,
        body: JSON.stringify({
          error: "Invalid JSON",
          code: ERROR_CODE.BAD_REQUEST,
          source: ERROR_SOURCE.PROXY,
        }),
        headers: JSON_HEADER,
      };
    }
  }

  // Whitelist the base URL (DA-03): never let a caller-supplied value point
  // this proxy at an arbitrary host.
  if (!isAllowedAlpacaBaseUrl(baseUrl)) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        error: "Invalid baseUrl. Must be an Alpaca REST endpoint.",
        code: ERROR_CODE.BAD_REQUEST,
        source: ERROR_SOURCE.PROXY,
      }),
      headers: JSON_HEADER,
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

      // The admin key was already accepted by requireAdmin() above, so a
      // rejection HERE is an UPSTREAM (broker) failure — it must never be
      // surfaced to the UI as a local admin-auth 401. Remap an upstream
      // 401/403 to 502 Bad Gateway so a bare 401 from this endpoint always
      // and only means "your admin key is bad". The precise upstream status
      // is preserved in the body for diagnostics.
      const isUpstreamAuth = response.status === 401 || response.status === 403;
      const isPaper = baseUrl.includes('paper-api');
      return {
        statusCode: isUpstreamAuth ? 502 : response.status,
        body: JSON.stringify({
          error: isUpstreamAuth
            ? `Alpaca rejected the broker credentials (HTTP ${response.status}). ` +
              `Verify the API key/secret and that they are ${isPaper ? 'Paper' : 'Live'} ` +
              `keys matching the ${isPaper ? 'Paper' : 'Live'} base URL.`
            : errorMessage,
          code: isUpstreamAuth ? ERROR_CODE.ALPACA_AUTH : ERROR_CODE.ALPACA_UPSTREAM,
          source: ERROR_SOURCE.ALPACA,
          upstreamStatus: response.status,
          latency,
        }),
        headers: JSON_HEADER,
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
      statusCode: 502,
      body: JSON.stringify({
        error: `Could not reach Alpaca: ${String(err)}`,
        code: ERROR_CODE.PROXY_ERROR,
        source: ERROR_SOURCE.ALPACA,
        latency: Date.now() - startTime,
      }),
      headers: JSON_HEADER,
    }
  }
}

export { handler }
