# Doppler + Netlify Setup

1. Go to [doppler.com/integrations/netlify](https://doppler.com/integrations/netlify)
2. Connect Doppler project: `disrupting-alpha`
3. Select Environment: `production`
4. Select Netlify site: `disruptingalpha.com`
5. Enable auto-sync
6. Click "Sync Now" to push all secrets immediately
7. Verify in Netlify dashboard: Site settings → Environment variables — all keys should appear.

## Required Variables for Netlify
The Netlify dashboard requires the following variables to be synced from Doppler:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_DEFAULT_SYMBOL`
- `VITE_DEFAULT_TIMEFRAME`
- `ADMIN_API_KEY`
