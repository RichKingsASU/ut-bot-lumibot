
const { createClient } = require('@supabase/supabase-js');
const dotenv = require('dotenv');
const path = require('path');
const fs = require('fs');

// Simple manual env loader if dotenv fails or to be sure
const envPath = path.join(__dirname, '.env');
const envConfig = dotenv.config({ path: envPath });

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseServiceKey) {
  console.error('Supabase credentials missing in .env at', envPath);
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseServiceKey);

async function checkStatus() {
  console.log('--- Checking Supabase Data Inventory ---');
  console.log('Using URL:', supabaseUrl);
  
  try {
    console.log('Fetching bar_inventory...');
    const { data: barInventory, error: barError } = await supabase.from('bar_inventory').select('*');
    if (barError) console.error('Bar Inventory Error:', barError);
    else console.log('Bar Inventory:', (barInventory || []).length, 'records');

    const { data: optionsSummary, error: optError } = await supabase.from('options_chain_summary').select('*');
    if (optError) console.error('Options Summary Error:', optError);
    else console.log('Options Summary:', (optionsSummary || []).length, 'records');

    const { data: activeJobs, error: jobError } = await supabase
      .from('seed_jobs')
      .select('*')
      .order('started_at', { ascending: false })
      .limit(5);
    if (jobError) console.error('Seed Jobs Error:', jobError);
    else {
      console.log('Recent Seed Jobs:');
      (activeJobs || []).forEach(job => {
        console.log(`- [${job.status}] ${job.job_type} ${job.symbol} ${job.timeframe || ''} (${job.rows_written} rows at ${job.started_at})`);
      });
    }

    const { count: ohlcvCount } = await supabase.from('ohlcv_bars').select('*', { count: 'exact', head: true });
    const { count: optionsCount } = await supabase.from('options_chain').select('*', { count: 'exact', head: true });

    console.log(`Total OHLCV Bars: ${ohlcvCount}`);
    console.log(`Total Options Rows: ${optionsCount}`);
  } catch (e) {
    console.error('Critical check error:', e);
  }
}

checkStatus().catch(console.error);
