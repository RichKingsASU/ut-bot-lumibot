import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

const supabase = createClient(supabaseUrl, supabaseServiceKey);

export default async (req: Request) => {
    try {
        // 1. Bar inventory
        const { data: barInventory } = await supabase.from("bar_inventory").select("*");

        // 2. Options summary
        const { data: optionsSummary } = await supabase.from("options_chain_summary").select("*");

        // 3. Active jobs
        const { data: activeJobs } = await supabase
            .from("seed_jobs")
            .select("*")
            .order("started_at", { ascending: false })
            .limit(10);

        // 4. Storage estimate
        const { count: ohlcvCount } = await supabase.from("ohlcv_bars").select("*", { count: 'exact', head: true });
        const { count: optionsCount } = await supabase.from("options_chain").select("*", { count: 'exact', head: true });

        // Simple heuristic: ~150 bytes per OHLCV row, ~500 bytes per options row
        const ohlcvMb = ((ohlcvCount || 0) * 150) / (1024 * 1024);
        const optionsMb = ((optionsCount || 0) * 500) / (1024 * 1024);

        return new Response(JSON.stringify({
            bar_inventory: barInventory || [],
            options_summary: optionsSummary || [],
            active_jobs: activeJobs || [],
            storage_estimate: {
                ohlcv_row_count: ohlcvCount || 0,
                options_row_count: optionsCount || 0,
                approx_mb: Math.ceil(ohlcvMb + optionsMb)
            }
        }), { 
            status: 200,
            headers: { "Content-Type": "application/json" }
        });

    } catch (err: any) {
        console.error("[SEED-STATUS] Failure:", err);
        return new Response(JSON.stringify({ error: err.message }), { status: 500 });
    }
};
