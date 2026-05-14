import { Handler } from '@netlify/functions';
import axios from 'axios';
import { logAlert } from "./lib/alerts"

let lastFlattenTime = 0;
const FLATTEN_COOLDOWN = 30000; // 30s

export const handler: Handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  const now = Date.now();
  if (now - lastFlattenTime < FLATTEN_COOLDOWN) {
    return { 
      statusCode: 429, 
      body: JSON.stringify({ error: "A flatten operation was recently initiated. Please wait 30s before retrying." }) 
    };
  }

  const adminKey = event.headers['x-admin-api-key'];
  if (adminKey !== process.env.ADMIN_API_KEY) {
    return { statusCode: 401, body: 'Unauthorized' };
  }
  
  lastFlattenTime = now;

  const isPaper = process.env.ALPACA_IS_PAPER === 'true';
  const baseUrl = isPaper 
    ? 'https://paper-api.alpaca.markets' 
    : 'https://api.alpaca.markets';

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
