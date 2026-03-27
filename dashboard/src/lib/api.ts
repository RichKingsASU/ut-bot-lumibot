/**
 * Shared API endpoint helpers for Netlify Functions.
 *
 * Both local dev (netlify dev) and production serve functions at
 * /.netlify/functions/<name>, so no environment branching is needed.
 */

const BASE = '/.netlify/functions'

export const API = {
  optionsConfig: (action: string) =>
    `${BASE}/options-config?action=${action}`,
  botState: () => `${BASE}/bot-state`,
  botConfig: () => `${BASE}/bot-config`,
}
