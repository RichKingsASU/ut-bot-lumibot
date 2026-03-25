
const https = require('https');

const symbol = process.argv[2] || 'IWM';
const timeframe = process.argv[3] || '15Min';
const days = parseInt(process.argv[4]) || 730;

function trigger() {
  const data = JSON.stringify({ symbol, timeframe, days });
  const url = 'https://disruptingalpha.com/.netlify/functions/seed-bars-background';
  
  console.log(`Triggering ${timeframe} backfill for ${symbol} (${days} days) at ${url}...`);

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

  const req = https.request(options, (res) => {
    let responseBody = '';
    res.on('data', (d) => { responseBody += d; });
    res.on('end', () => {
      console.log(`Status code: ${res.statusCode}`);
      console.log('Response:', responseBody);
    });
  });

  req.on('error', (error) => {
    console.error('Error triggering backfill:', error);
  });

  req.write(data);
  req.end();
}

trigger();
