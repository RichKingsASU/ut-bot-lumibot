import { Context } from "@netlify/functions";

/**
 * Bot Config API — Netlify Function
 *
 * GET  /bot-config       → returns all bot_config rows as { key: value }
 * POST /bot-config       → accepts { key, value }, upserts to bot_config
 */

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

const JSON_HEADERS = { "Content-Type": "application/json", "Cache-Control": "no-store" };

const SUPABASE_HEADERS = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
  "Content-Type": "application/json",
};

export default async (req: Request, _context: Context) => {
  try {
    // ── POST: upsert a single key/value ──────────────────────────────
    if (req.method === "POST") {
      const body = await req.json();
      const { key, value } = body;

      if (!key || value === undefined || value === null) {
        return new Response(
          JSON.stringify({ error: "Missing key or value" }),
          { status: 400, headers: JSON_HEADERS }
        );
      }

      const res = await fetch(`${SUPABASE_URL}/rest/v1/bot_config`, {
        method: "POST",
        headers: {
          ...SUPABASE_HEADERS,
          Prefer: "resolution=merge-duplicates,return=representation",
        },
        body: JSON.stringify({
          key: String(key),
          value: String(value),
          updated_at: new Date().toISOString(),
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        return new Response(
          JSON.stringify({ error: `Supabase write failed: ${text}` }),
          { status: 500, headers: JSON_HEADERS }
        );
      }

      const rows = await res.json();
      const row = Array.isArray(rows) ? rows[0] : rows;
      return new Response(
        JSON.stringify({ status: "ok", row }),
        { status: 200, headers: JSON_HEADERS }
      );
    }

    // ── GET: return all bot_config rows as { key: value } dict ───────
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/bot_config?select=key,value,updated_at&order=id.asc`,
      { headers: SUPABASE_HEADERS }
    );

    if (!res.ok) {
      const text = await res.text();
      return new Response(
        JSON.stringify({ error: `Supabase read failed: ${text}` }),
        { status: 500, headers: JSON_HEADERS }
      );
    }

    const rows: { key: string; value: string; updated_at: string }[] = await res.json();
    const config: Record<string, string> = {};
    let lastUpdated: string | null = null;

    for (const row of rows) {
      config[row.key] = row.value;
      if (!lastUpdated || row.updated_at > lastUpdated) {
        lastUpdated = row.updated_at;
      }
    }

    return new Response(
      JSON.stringify({ config, updated_at: lastUpdated }),
      { status: 200, headers: JSON_HEADERS }
    );
  } catch (err: any) {
    console.error("[bot-config] Error:", err);
    return new Response(
      JSON.stringify({ error: err.message || String(err) }),
      { status: 500, headers: JSON_HEADERS }
    );
  }
};
