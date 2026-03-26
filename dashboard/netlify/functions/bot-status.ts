import { Context } from "@netlify/functions";

/**
 * Bot Status API — reads the heartbeat row from Supabase bot_status
 * and computes real online/offline/stale state from heartbeat staleness.
 */

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

const STALE_THRESHOLD_SECONDS = 90;

const JSON_HEADERS = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default async (req: Request, _context: Context) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: JSON_HEADERS });
  }

  try {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/bot_status?id=eq.1&select=*`,
      {
        headers: {
          apikey: SUPABASE_KEY,
          Authorization: `Bearer ${SUPABASE_KEY}`,
        },
      }
    );

    if (!res.ok) {
      return new Response(
        JSON.stringify({ online: false, status: "error", error: `Supabase HTTP ${res.status}` }),
        { status: 200, headers: JSON_HEADERS }
      );
    }

    const rows = await res.json();
    if (!rows || rows.length === 0) {
      return new Response(
        JSON.stringify({ online: false, status: "offline", error: "no status row" }),
        { status: 200, headers: JSON_HEADERS }
      );
    }

    const row = rows[0];
    const lastHeartbeat = row.last_heartbeat ? new Date(row.last_heartbeat) : null;
    const now = new Date();
    const secondsSinceHeartbeat = lastHeartbeat
      ? Math.floor((now.getTime() - lastHeartbeat.getTime()) / 1000)
      : null;

    // Determine real status from heartbeat staleness
    let online = false;
    let status = "offline";

    if (lastHeartbeat && secondsSinceHeartbeat !== null) {
      if (secondsSinceHeartbeat <= STALE_THRESHOLD_SECONDS) {
        online = true;
        status = "online";
      } else if (row.status === "online") {
        // Bot claims online but heartbeat is stale — crashed or network issue
        status = "stale";
      } else {
        status = "offline";
      }
    }

    return new Response(
      JSON.stringify({
        online,
        status,
        last_heartbeat: row.last_heartbeat,
        session_id: row.session_id,
        symbol: row.symbol,
        mode: row.mode,
        uptime_seconds: row.uptime_seconds,
        last_signal: row.last_signal,
        last_signal_time: row.last_signal_time,
        seconds_since_heartbeat: secondsSinceHeartbeat,
      }),
      { status: 200, headers: JSON_HEADERS }
    );
  } catch (err: any) {
    return new Response(
      JSON.stringify({ online: false, status: "error", error: err.message }),
      { status: 200, headers: JSON_HEADERS }
    );
  }
};
