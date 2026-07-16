import { Handler } from '@netlify/functions';
import axios from 'axios';
import { logAlert, setBotTargetStatus } from "./lib/alerts"
import { requireAdmin, resolveIsPaper, alpacaBaseUrl } from "./lib/auth"

let lastFlattenTime = 0;
const FLATTEN_COOLDOWN = 30000; // 30s

export const handler: Handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  // Fail-CLOSED admin auth (DA-06): a request with no valid admin key — or a
  // deployed environment with no ADMIN_API_KEY configured — is refused.
  const auth = requireAdmin(event);
  if (!auth.ok) {
    return { statusCode: auth.statusCode, body: auth.body };
  }

  // Safe default (DA-02): PAPER unless ALPACA_IS_PAPER is explicitly "false".
  // A missing/blank env var must never resolve the flatten to the LIVE account.
  const isPaper = resolveIsPaper();
  const baseUrl = alpacaBaseUrl(isPaper);

  // Live flatten requires an explicit typed confirmation in the body (DA-02):
  // { "confirm": "LIVE" }. Paper flatten needs no confirmation.
  if (!isPaper) {
    let confirm: unknown;
    try {
      confirm = event.body ? JSON.parse(event.body).confirm : undefined;
    } catch {
      return { statusCode: 400, body: JSON.stringify({ error: "Invalid JSON body." }) };
    }
    if (confirm !== "LIVE") {
      return {
        statusCode: 428, // Precondition Required
        body: JSON.stringify({
          error: 'Live flatten requires explicit confirmation. Resend with body {"confirm":"LIVE"}.',
          environment: "live",
        }),
      };
    }
  }

  const now = Date.now();
  if (now - lastFlattenTime < FLATTEN_COOLDOWN) {
    return {
      statusCode: 429,
      body: JSON.stringify({ error: "A flatten operation was recently initiated. Please wait 30s before retrying." })
    };
  }
  lastFlattenTime = now;

  const headers = {
    'APCA-API-KEY-ID': process.env.ALPACA_API_KEY,
    'APCA-API-SECRET-KEY': process.env.ALPACA_API_SECRET,
  };

  try {
    console.log(`[FLATTEN] Initiating emergency shutdown. Environment: ${isPaper ? 'PAPER' : 'LIVE'}`);

    await logAlert(
      `Emergency Flatten Initiated via Dashboard! Target: ${isPaper ? 'PAPER' : 'LIVE'}`,
      "CRITICAL",
      "RISK"
    );

    // 1. Cancel all open orders
    await axios.delete(`${baseUrl}/v2/orders`, { headers });
    console.log('[FLATTEN] All open orders cancelled.');

    // 2. Close all open positions
    await axios.delete(`${baseUrl}/v2/positions`, { headers });
    console.log('[FLATTEN] All open positions liquidation initiated.');

    // 3. Signal bot to shutdown
    const signalSent = await setBotTargetStatus('shutdown');
    if (signalSent) {
      console.log('[FLATTEN] Bot shutdown signal sent to Supabase.');
    }

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Emergency flatten initiated successfully.',
        environment: isPaper ? 'paper' : 'live',
      }),
    };
  } catch (error: any) {
    console.error('[FLATTEN] Error during emergency shutdown:', error.response?.data || error.message);
    
    await logAlert(
      `Emergency Flatten FAILED: ${error.message}`,
      "CRITICAL",
      "RISK",
      { error: error.response?.data || error.message }
    );

    return {
      statusCode: 500,
      body: JSON.stringify({
        error: 'Failed to initiate flatten.',
      }),
    };
  }
};
