import { Context } from "@netlify/functions";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

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

  try {
    const now = new Date();
    const todayStart = new Date(now);
    todayStart.setUTCHours(0, 0, 0, 0);
    const todayISO = todayStart.toISOString();

    // bar_log stats
    const { count: barTotal } = await supabase
      .from("bar_log")
      .select("*", { count: "exact", head: true });

    const { data: latestBar } = await supabase
      .from("bar_log")
      .select("bar_time")
      .order("bar_time", { ascending: false })
      .limit(1);

    const { count: barsToday } = await supabase
      .from("bar_log")
      .select("*", { count: "exact", head: true })
      .gte("created_at", todayISO);

    const latestBarTime = latestBar?.[0]?.bar_time || null;
    const secondsSinceLastBar = latestBarTime
      ? Math.round((now.getTime() - new Date(latestBarTime).getTime()) / 1000)
      : null;

    // signal_log stats
    const { count: signalTotal } = await supabase
      .from("signal_log")
      .select("*", { count: "exact", head: true });

    const { data: latestSignal } = await supabase
      .from("signal_log")
      .select("bar_time")
      .order("bar_time", { ascending: false })
      .limit(1);

    const { count: signalsToday } = await supabase
      .from("signal_log")
      .select("*", { count: "exact", head: true })
      .gte("created_at", todayISO);

    // paper_trades stats
    const { count: tradeTotal } = await supabase
      .from("paper_trades")
      .select("*", { count: "exact", head: true });

    const { count: tradesToday } = await supabase
      .from("paper_trades")
      .select("*", { count: "exact", head: true })
      .gte("created_at", todayISO)
      .eq("side", "EXIT");

    const { data: todayPnl } = await supabase
      .from("paper_trades")
      .select("trade_pnl")
      .gte("created_at", todayISO)
      .eq("side", "EXIT")
      .not("trade_pnl", "is", null);

    const pnlToday = (todayPnl || []).reduce(
      (sum: number, t: any) => sum + (t.trade_pnl || 0),
      0
    );

    // sessions stats
    const { data: activeSession } = await supabase
      .from("sessions")
      .select("session_id, started_at")
      .eq("status", "running")
      .order("started_at", { ascending: false })
      .limit(1);

    const result = {
      bar_log: {
        total_rows: barTotal || 0,
        latest_bar: latestBarTime,
        seconds_since_last_bar: secondsSinceLastBar,
        rows_today: barsToday || 0,
      },
      signal_log: {
        total_rows: signalTotal || 0,
        latest_signal: latestSignal?.[0]?.bar_time || null,
        signals_today: signalsToday || 0,
      },
      paper_trades: {
        total_rows: tradeTotal || 0,
        trades_today: tradesToday || 0,
        pnl_today: Math.round(pnlToday * 100) / 100,
      },
      sessions: {
        active_session_id: activeSession?.[0]?.session_id || null,
        session_started: activeSession?.[0]?.started_at || null,
      },
    };

    return new Response(JSON.stringify(result, null, 2), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    console.error("[DATA-HEALTH] Error:", err);
    return new Response(
      JSON.stringify({ error: err.message }),
      { status: 500 }
    );
  }
};
