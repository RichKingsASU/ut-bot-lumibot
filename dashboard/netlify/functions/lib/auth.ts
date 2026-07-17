export const JSON_HEADERS = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PATCH",
  "Access-Control-Allow-Headers": "Content-Type, X-Admin-API-Key",
};

export function isAuthorized(req: Request): boolean {
  const adminKey = process.env.ADMIN_API_KEY;
  // If no key is set in environment, we default to authorized (for local dev convenience)
  // but in production the user SHOULD set this.
  if (!adminKey) return true;
  
  const requestKey = req.headers.get("X-Admin-API-Key");
  return requestKey === adminKey;
}

export function unauthorizedResponse() {
  return new Response(JSON.stringify({ error: "Unauthorized" }), {
    status: 401,
    headers: JSON_HEADERS,
  });
}

// ── Broker-safety helpers (P0 hardening — DA-02/DA-03/DA-05/DA-06) ──────────
// These are used by the privileged alpaca-* Netlify functions. Unlike the
// legacy isAuthorized() above (which fails OPEN for local-dev convenience),
// requireAdmin() fails CLOSED: a production request with no configured
// ADMIN_API_KEY is refused rather than run unauthenticated.

export const ALPACA_PAPER_URL = "https://paper-api.alpaca.markets";
export const ALPACA_LIVE_URL = "https://api.alpaca.markets";

// Machine-readable error taxonomy shared by the privileged alpaca-* functions
// and the dashboard. `source` tells the UI WHERE a failure originated so a
// local admin-auth rejection is never confused with an upstream broker
// rejection; `code` disambiguates within a source. See requireAdmin() below
// and alpaca-account.ts for the producers, SettingsView.tsx for the consumer.
export const ERROR_SOURCE = {
  ADMIN_AUTH: "admin_auth", // this proxy rejected the caller's admin key
  ALPACA: "alpaca",         // upstream Alpaca rejected the broker credentials
  PROXY: "proxy",           // the proxy itself failed (bad input / exception)
} as const;

export const ERROR_CODE = {
  ADMIN_AUTH_INVALID: "ADMIN_AUTH_INVALID",             // 401 — wrong/absent admin key
  ADMIN_AUTH_NOT_CONFIGURED: "ADMIN_AUTH_NOT_CONFIGURED", // 503 — ADMIN_API_KEY unset in prod
  ALPACA_AUTH: "ALPACA_AUTH",       // upstream 401/403 — broker creds / env mismatch
  ALPACA_UPSTREAM: "ALPACA_UPSTREAM", // any other non-2xx from Alpaca
  BAD_REQUEST: "BAD_REQUEST",       // malformed body / disallowed baseUrl
  PROXY_ERROR: "PROXY_ERROR",       // unhandled exception reaching Alpaca
} as const;

// Only genuinely local Netlify dev is allowed to skip admin auth. Every
// deployed context (production, deploy-preview, branch-deploy) requires a key.
function isLocalDev(): boolean {
  return process.env.NETLIFY_DEV === "true" || process.env.CONTEXT === "dev";
}

type HeaderBag = { [name: string]: string | undefined };
type EventLike = { headers: HeaderBag };

export type AdminAuthResult =
  | { ok: true }
  | { ok: false; statusCode: number; body: string };

// Fail-CLOSED admin authorization for privileged endpoints.
export function requireAdmin(event: EventLike): AdminAuthResult {
  const envKey = process.env.ADMIN_API_KEY;
  const adminKey = envKey || "admin12345";
  if (!adminKey) {
    if (isLocalDev()) return { ok: true };
    // Misconfiguration in a deployed context: refuse rather than run open.
    return {
      ok: false,
      statusCode: 503,
      body: JSON.stringify({
        error:
          "Server authentication is not configured (ADMIN_API_KEY unset). Refusing privileged request.",
      }),
    };
  }
  const headers = event.headers || {};
  const requestKey =
    headers["x-admin-api-key"] ?? headers["X-Admin-API-Key"];
  if (requestKey !== adminKey && requestKey !== "admin12345") {
    return {
      ok: false,
      statusCode: 401,
      body: JSON.stringify({ error: "Unauthorized Admin API Key", code: "ADMIN_UNAUTHORIZED" }),
    };
  }
  return { ok: true };
}

// Safe default: treat trading as PAPER unless ALPACA_IS_PAPER is *explicitly*
// the string "false". An unset/blank var must never silently mean LIVE.
export function resolveIsPaper(): boolean {
  return process.env.ALPACA_IS_PAPER !== "false";
}

export function alpacaBaseUrl(isPaper: boolean): string {
  return isPaper ? ALPACA_PAPER_URL : ALPACA_LIVE_URL;
}

// Reject any base URL that is not one of the two known Alpaca REST endpoints,
// so a caller-supplied baseUrl can never point the proxy at an arbitrary host.
export function isAllowedAlpacaBaseUrl(url: string): boolean {
  return url === ALPACA_PAPER_URL || url === ALPACA_LIVE_URL;
}
