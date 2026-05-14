import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

export default async (req: Request, context: Context) => {
  // ── [SECURITY FIX] Admin Auth ──────────────────────────────────────
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = req.headers.get('x-admin-api-key');
  if (adminKey && requestKey !== adminKey) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), { 
      status: 401,
      headers: { "Content-Type": "application/json" }
    });
  }

  const supabaseUrl = process.env.SUPABASE_URL!;
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  const supabase = createClient(supabaseUrl, supabaseKey);

  const tables = ["bar_log", "signal_log", "paper_trades", "sessions"];
  const results: Record<string, { exists: boolean; rows: number }> = {};

  for (const table of tables) {
    try {
      const { count, error } = await supabase
        .from(table)
        .select("*", { count: "exact", head: true });

      if (error) {
        results[table] = { exists: false, rows: 0 };
      } else {
        results[table] = { exists: true, rows: count || 0 };
      }
    } catch (err) {
      console.error(`[bootstrap-tables] Error checking table ${table}:`, err);
      results[table] = { exists: false, rows: 0 };
    }
  }

  const allExist = Object.values(results).every((r) => r.exists);
  const missing = Object.entries(results)
    .filter(([, r]) => !r.exists)
    .map(([name]) => name);

  const response = {
    status: allExist ? "ready" : "tables_missing",
    tables: results,
    ...(missing.length > 0 && {
      action_required:
        `Run this SQL in the Supabase SQL Editor: ` +
        `dashboard/supabase/migrations/20260326000000_streaming_tables.sql`,
      missing_tables: missing,
    }),
  };

  return new Response(JSON.stringify(response, null, 2), {
    status: allExist ? 200 : 424,
    headers: { "Content-Type": "application/json" },
  });
};
