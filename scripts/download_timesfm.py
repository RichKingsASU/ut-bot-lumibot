#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv('/home/k2/ut-bot-lumibot/.env')

token = os.getenv('HUGGINGFACE_TOKEN')
if not token:
    print('❌ HUGGINGFACE_TOKEN not in .env')
    print('Get token from huggingface.co/settings/tokens')
    exit(1)

print('Downloading TimesFM model (~800MB)...')
from huggingface_hub import snapshot_download
path = snapshot_download(
    repo_id='google/timesfm-1.0-200m',
    token=token,
    local_dir='/home/k2/timesfm-model'
)
print(f'✅ Model downloaded to {path}')
print('Restart agents session to activate TimesFM')
