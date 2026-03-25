
const https = require('https');

const symbols = ['IWM', 'SPY', 'QQQ'];
const timeframes = ['1Min', '5Min', '15Min', '1Hour', '1Day'];
const days = 730;

function triggerOne(symbol, timeframe) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ symbol, timeframe, days });
    const options = {
      hostname: 'disruptingalpha.com',
      port: 443,
      path: '/.netlify/functions/seed-bars-background',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': data.length
      }
    };

    console.log(`Triggering ${timeframe} for ${symbol}...`);
    const req = https.request(options, (res) => {
      resolve(res.statusCode);
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function triggerAll() {
  for (const symbol of symbols) {
    for (const timeframe of timeframes) {
      if (symbol === 'IWM' && timeframe === '15Min') continue; // Already done
      try {
        const status = await triggerOne(symbol, timeframe);
        console.log(`- ${symbol} ${timeframe}: ${status}`);
        // Wait a bit between triggers to avoid overwhelming the dashboard/functions list
        await new Promise(r => setTimeout(r, 2000));
      } catch (err) {
        console.error(`Failed ${symbol} ${timeframe}:`, err.message);
      }
    }
  }
  console.log('All triggers sent.');
}

triggerAll();
