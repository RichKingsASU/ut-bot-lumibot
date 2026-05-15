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
