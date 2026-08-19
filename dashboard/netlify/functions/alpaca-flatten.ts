import { Handler } from '@netlify/functions';
import { requireAdmin } from "./lib/auth"

/**
 * Direct dashboard-to-broker mutation is intentionally retired.
 *
 * Netlify cannot own the edge host's account-scoped kernel lease, so allowing
 * this function to cancel/close would violate the single-writer invariant.
 */
export const handler: Handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  const auth = requireAdmin(event);
  if (!auth.ok) {
    return { statusCode: auth.statusCode, body: auth.body };
  }

  return {
    statusCode: 410,
    body: JSON.stringify({
      error: 'Direct broker flatten is disabled. Use the canonical edge executor control path.',
    }),
  };
};
