#!/usr/bin/env python3
"""
Run with: doppler run -- python scripts/verify-doppler.py
Verifies all required env vars are present and non-empty.
"""
import os, sys

REQUIRED = [
    # Alpaca
    'ALPACA_API_KEY', 'ALPACA_API_SECRET', 'ALPACA_BASE_URL',
    'ALPACA_DATA_URL', 'ALPACA_STREAM_URL',
    # Supabase
    'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY',
    # Anthropic
    'ANTHROPIC_API_KEY_AGENTS',
    'ANTHROPIC_API_KEY_SENTIMENT', 
    'ANTHROPIC_API_KEY_HERMES',
    # Security
    'ADMIN_API_KEY',
    # Finnhub
    'FINNHUB_API_KEY',
    # Risk
    'MAX_DAILY_LOSS', 'MAX_POSITION_SIZE', 'MAX_TRADES_PER_DAY',
    # Dashboard
    'VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY',
]

OPTIONAL = [
    'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USER_AGENT',
]

missing = []
for key in REQUIRED:
    val = os.getenv(key)
    if not val or val.startswith('your-'):
        missing.append(key)
        print(f'FAIL: {key} missing or placeholder')
    else:
        print(f'PASS: {key}')

for key in OPTIONAL:
    val = os.getenv(key)
    status = 'PASS' if val and not val.startswith('your-') else 'WARN (optional)'
    print(f'{status}: {key}')

if missing:
    print(f'\n{len(missing)} required secrets missing. Fix before removing .env')
    sys.exit(1)
else:
    print('\nAll required secrets present. Safe to remove .env from disk.')
    sys.exit(0)
