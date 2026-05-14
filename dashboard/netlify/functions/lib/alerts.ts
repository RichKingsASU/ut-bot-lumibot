import { createClient } from "@supabase/supabase-js";

let cachedClient: ReturnType<typeof createClient> | null = null;

function getSupabase() {
  if (cachedClient) return cachedClient;
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  cachedClient = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return cachedClient;
}

export async function logAlert(
  message: string,
  severity: string = "INFO",
  type: string = "GENERAL",
  metadata?: Record<string, unknown>
): Promise<boolean> {
  const supabase = getSupabase();
  if (!supabase) {
    console.warn("[logAlert] Supabase env missing; skipping insert.", { message, severity, type });
    return false;
  }
  try {
    const { error } = await supabase.from("alerts").insert({
      message,
      severity,
      type,
      metadata: metadata ?? null,
      created_at: new Date().toISOString(),
    });
    if (error) {
      console.error("[logAlert] insert error:", error.message);
      return false;
    }
    return true;
  } catch (e) {
    console.error("[logAlert] failed:", e);
    return false;
  }
}

export async function setBotTargetStatus(
  status: string,
  symbol: string = "IWM"
): Promise<boolean> {
  const supabase = getSupabase();
  if (!supabase) {
    console.warn("[setBotTargetStatus] Supabase env missing; skipping upsert.", { status, symbol });
    return false;
  }
  try {
    const { error } = await supabase
      .from("bot_status")
      .upsert(
        {
          symbol,
          target_status: status,
          updated_at: new Date().toISOString(),
        },
        { onConflict: "symbol" }
      );
    if (error) {
      console.error("[setBotTargetStatus] upsert error:", error.message);
      return false;
    }
    return true;
  } catch (e) {
    console.error("[setBotTargetStatus] failed:", e);
    return false;
  }
}
