import { Context } from "@netlify/functions";

/**
 * Options Config API — Netlify Function
 *
 * Actions (via ?action= query param):
 *   GET  ?action=get          → current options config
 *   POST ?action=save         → save config to Supabase user_settings
 *   GET  ?action=preview      → live contract preview from Alpaca
 *   GET  ?action=expirations  → next 10 available SPY expirations
 */

const ALPACA_DATA_URL = process.env.ALPACA_DATA_URL || "https://data.alpaca.markets";
const ALPACA_API_KEY = process.env.ALPACA_API_KEY || "";
const ALPACA_API_SECRET = process.env.ALPACA_API_SECRET || "";

const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

const JSON_HEADERS = { "Content-Type": "application/json", "Cache-Control": "no-store" };

const ALPACA_HEADERS = {
  "APCA-API-KEY-ID": ALPACA_API_KEY,
  "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
  "Content-Type": "application/json",
};

// ── Defaults ────────────────────────────────────────────────────────────────
const DEFAULTS: OptionsConfig = {
  expiration_mode: "0DTE",
  expiration_days_out: 0,
  strike_mode: "ATM",
  strike_step: 1.0,
  max_dte_fallback: 7,
};

interface OptionsConfig {
  expiration_mode: string;
  expiration_days_out: number;
  strike_mode: string;
  strike_step: number;
  max_dte_fallback: number;
}

const VALID_EXPIRATION_MODES = ["0DTE", "1DTE", "2DTE", "WEEKLY", "BIWEEKLY", "MONTHLY", "CUSTOM"];
const VALID_STRIKE_MODES = ["ITM3", "ITM2", "ITM1", "ATM", "OTM1", "OTM2", "OTM3"];

// ── Supabase helpers ────────────────────────────────────────────────────────

async function supabaseGet(table: string, key: string): Promise<any> {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/${table}?key=eq.${key}&select=value&limit=1`,
    {
      headers: {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        "Content-Type": "application/json",
      },
    }
  );
  if (!res.ok) return null;
  const rows = await res.json();
  return rows.length > 0 ? rows[0].value : null;
}

async function supabaseUpsert(table: string, key: string, value: any): Promise<boolean> {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}`, {
    method: "POST",
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates",
    },
    body: JSON.stringify({ key, value }),
  });
  return res.ok;
}

// ── Config CRUD ─────────────────────────────────────────────────────────────

async function getConfig(): Promise<OptionsConfig> {
  try {
    const stored = await supabaseGet("user_settings", "options_config");
    if (stored && typeof stored === "object") {
      return { ...DEFAULTS, ...stored };
    }
  } catch (e) {
    console.error("[options-config] Supabase read failed:", e);
  }
  return { ...DEFAULTS };
}

async function saveConfig(body: any): Promise<{ config: OptionsConfig; error?: string }> {
  const current = await getConfig();
  const updated = { ...current };

  if (body.expiration_mode !== undefined) {
    if (!VALID_EXPIRATION_MODES.includes(body.expiration_mode)) {
      return { config: current, error: `Invalid expiration_mode. Must be one of: ${VALID_EXPIRATION_MODES.join(", ")}` };
    }
    updated.expiration_mode = body.expiration_mode;
  }
  if (body.strike_mode !== undefined) {
    if (!VALID_STRIKE_MODES.includes(body.strike_mode)) {
      return { config: current, error: `Invalid strike_mode. Must be one of: ${VALID_STRIKE_MODES.join(", ")}` };
    }
    updated.strike_mode = body.strike_mode;
  }
  if (body.expiration_days_out !== undefined) {
    const d = Number(body.expiration_days_out);
    if (isNaN(d) || d < 0 || d > 60) {
      return { config: current, error: "expiration_days_out must be 0-60" };
    }
    updated.expiration_days_out = d;
  }
  if (body.strike_step !== undefined) {
    const s = Number(body.strike_step);
    if (isNaN(s) || s < 0.5 || s > 10) {
      return { config: current, error: "strike_step must be 0.5-10" };
    }
    updated.strike_step = s;
  }
  if (body.max_dte_fallback !== undefined) {
    const m = Number(body.max_dte_fallback);
    if (isNaN(m) || m < 0 || m > 60) {
      return { config: current, error: "max_dte_fallback must be 0-60" };
    }
    updated.max_dte_fallback = m;
  }

  const ok = await supabaseUpsert("user_settings", "options_config", updated);
  if (!ok) {
    return { config: current, error: "Failed to write to Supabase" };
  }
  return { config: updated };
}

// ── Alpaca helpers ──────────────────────────────────────────────────────────

function todayET(): string {
  const now = new Date();
  const et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
  return et.toISOString().slice(0, 10);
}

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr + "T12:00:00Z");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function computeTargetExpiration(config: OptionsConfig): string {
  const today = todayET();
  switch (config.expiration_mode) {
    case "0DTE": return today;
    case "1DTE": return addDays(today, 1);
    case "2DTE": return addDays(today, 2);
    case "WEEKLY": {
      const d = new Date(today + "T12:00:00Z");
      const dayOfWeek = d.getUTCDay();
      const daysUntilFri = (5 - dayOfWeek + 7) % 7 || 7;
      return addDays(today, daysUntilFri);
    }
    case "BIWEEKLY": {
      const d = new Date(today + "T12:00:00Z");
      const dayOfWeek = d.getUTCDay();
      const daysUntilFri = (5 - dayOfWeek + 7) % 7 || 7;
      return addDays(today, daysUntilFri + 7);
    }
    case "MONTHLY": {
      const d = new Date(today + "T12:00:00Z");
      const year = d.getUTCFullYear();
      const month = d.getUTCMonth();
      // 3rd Friday of next month
      const nextMonth = month === 11 ? 0 : month + 1;
      const nextYear = month === 11 ? year + 1 : year;
      const first = new Date(Date.UTC(nextYear, nextMonth, 1));
      const firstDay = first.getUTCDay();
      const firstFri = firstDay <= 5 ? (5 - firstDay + 1) : (5 + 7 - firstDay + 1);
      const thirdFri = firstFri + 14;
      return `${nextYear}-${String(nextMonth + 1).padStart(2, "0")}-${String(thirdFri).padStart(2, "0")}`;
    }
    case "CUSTOM":
      return addDays(today, config.expiration_days_out);
    default:
      return today;
  }
}

function computeStrikeOffset(config: OptionsConfig): number {
  const step = config.strike_step;
  switch (config.strike_mode) {
    case "ITM3": return -3 * step;
    case "ITM2": return -2 * step;
    case "ITM1": return -1 * step;
    case "ATM":  return 0;
    case "OTM1": return 1 * step;
    case "OTM2": return 2 * step;
    case "OTM3": return 3 * step;
    default: return 0;
  }
}

async function fetchUnderlyingPrice(symbol: string = "SPY"): Promise<number | null> {
  try {
    const res = await fetch(`${ALPACA_DATA_URL}/v2/stocks/${symbol}/trades/latest`, {
      headers: ALPACA_HEADERS,
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data?.trade?.p ?? null;
  } catch {
    return null;
  }
}

async function fetchContracts(
  underlying: string,
  expirationDate: string,
  optionType: string = "call"
): Promise<any[]> {
  try {
    const params = new URLSearchParams({
      underlying_symbols: underlying,
      expiration_date: expirationDate,
      type: optionType,
      status: "active",
      limit: "200",
    });
    const res = await fetch(`${ALPACA_DATA_URL}/v2/options/contracts?${params}`, {
      headers: ALPACA_HEADERS,
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.option_contracts ?? data?.contracts ?? [];
  } catch {
    return [];
  }
}

async function fetchOptionQuote(contractSymbol: string): Promise<{ bid: number; ask: number } | null> {
  try {
    const params = new URLSearchParams({ symbols: contractSymbol, feed: "indicative" });
    const res = await fetch(`${ALPACA_DATA_URL}/v2/options/quotes/latest?${params}`, {
      headers: ALPACA_HEADERS,
    });
    if (!res.ok) return null;
    const data = await res.json();
    const q = data?.quotes?.[contractSymbol] ?? {};
    return { bid: Number(q.bp ?? 0), ask: Number(q.ap ?? 0) };
  } catch {
    return null;
  }
}

// ── Preview ─────────────────────────────────────────────────────────────────

async function getPreview(optionType: string = "call"): Promise<any> {
  const config = await getConfig();
  const underlying = "SPY";
  const price = await fetchUnderlyingPrice(underlying);
  if (price === null) {
    return { status: "unavailable", reason: "Could not fetch underlying price — market may be closed" };
  }

  let targetExp = computeTargetExpiration(config);
  let contracts = await fetchContracts(underlying, targetExp, optionType);

  // Fallback: search forward up to max_dte_fallback days
  if (contracts.length === 0 && config.max_dte_fallback > 0) {
    for (let d = 1; d <= config.max_dte_fallback; d++) {
      const fallbackDate = addDays(targetExp, d);
      contracts = await fetchContracts(underlying, fallbackDate, optionType);
      if (contracts.length > 0) {
        targetExp = fallbackDate;
        break;
      }
    }
  }

  if (contracts.length === 0) {
    return { status: "unavailable", reason: `No ${optionType} contracts found for ${underlying} near ${targetExp}` };
  }

  // Select strike with offset
  const offset = computeStrikeOffset(config);
  const targetStrike = Math.round(price) + offset;
  const best = contracts.reduce((a: any, b: any) =>
    Math.abs(Number(a.strike_price) - targetStrike) <= Math.abs(Number(b.strike_price) - targetStrike) ? a : b
  );

  const contractSymbol = best.symbol;
  const strike = Number(best.strike_price);
  const expiration = best.expiration_date;

  // DTE
  const today = new Date(todayET() + "T12:00:00Z");
  const expDate = new Date(expiration + "T12:00:00Z");
  const dte = Math.round((expDate.getTime() - today.getTime()) / (86400000));

  // Quote
  const quote = await fetchOptionQuote(contractSymbol);
  const bid = quote?.bid ?? 0;
  const ask = quote?.ask ?? 0;
  const mid = (bid + ask) / 2;

  return {
    symbol: contractSymbol,
    underlying_price: price,
    strike,
    expiration,
    dte,
    option_type: optionType,
    bid: Number(bid.toFixed(2)),
    ask: Number(ask.toFixed(2)),
    mid: Number(mid.toFixed(3)),
    expiration_mode_used: config.expiration_mode,
    strike_mode_used: config.strike_mode,
    status: "ok",
  };
}

// ── Expirations ─────────────────────────────────────────────────────────────

async function getExpirations(): Promise<any> {
  const underlying = "SPY";
  const today = todayET();
  const expirations: { date: string; dte: number; label: string }[] = [];

  // Check the next 30 calendar days for available contracts
  for (let d = 0; d <= 30 && expirations.length < 10; d++) {
    const date = addDays(today, d);
    const contracts = await fetchContracts(underlying, date, "call");
    if (contracts.length > 0) {
      const expDate = new Date(date + "T12:00:00Z");
      const dayOfWeek = expDate.getUTCDay();
      const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const isWeekly = dayOfWeek === 5;
      let label = d === 0
        ? `Today (0 DTE)`
        : `${dayNames[dayOfWeek]} ${monthNames[expDate.getUTCMonth()]} ${expDate.getUTCDate()} (${d} DTE)`;
      if (isWeekly && d > 0) label += " — Weekly";
      expirations.push({ date, dte: d, label });
    }
  }

  return { expirations };
}

// ── Main handler ────────────────────────────────────────────────────────────

export default async (req: Request, _context: Context) => {
  // ── [SECURITY FIX] Admin Auth ──────────────────────────────────────
  const adminKey = process.env.ADMIN_API_KEY;
  const requestKey = req.headers.get("X-Admin-API-Key");
  if (adminKey && requestKey !== adminKey) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: JSON_HEADERS,
    });
  }

  const url = new URL(req.url);
  const action = url.searchParams.get("action") || "get";

  try {
    // POST: save config
    if (req.method === "POST" && action === "save") {
      const body = await req.json();
      const { config, error } = await saveConfig(body);
      if (error) {
        return new Response(JSON.stringify({ status: "error", error, config }), {
          status: 400,
          headers: JSON_HEADERS,
        });
      }
      return new Response(JSON.stringify({ status: "ok", config }), {
        status: 200,
        headers: JSON_HEADERS,
      });
    }

    // GET: current config
    if (action === "get") {
      const config = await getConfig();
      return new Response(JSON.stringify(config), {
        status: 200,
        headers: JSON_HEADERS,
      });
    }

    // GET: preview
    if (action === "preview") {
      const optionType = url.searchParams.get("option_type") || "call";
      const preview = await getPreview(optionType);
      return new Response(JSON.stringify(preview), {
        status: 200,
        headers: JSON_HEADERS,
      });
    }

    // GET: expirations
    if (action === "expirations") {
      const data = await getExpirations();
      return new Response(JSON.stringify(data), {
        status: 200,
        headers: JSON_HEADERS,
      });
    }

    return new Response(JSON.stringify({ error: "Unknown action" }), {
      status: 400,
      headers: JSON_HEADERS,
    });
  } catch (err: any) {
    console.error("[options-config] Error:", err);
    return new Response(
      JSON.stringify({ status: "error", error: err.message || String(err) }),
      { status: 500, headers: JSON_HEADERS }
    );
  }
};
