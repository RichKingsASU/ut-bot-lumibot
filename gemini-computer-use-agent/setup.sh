#!/usr/bin/env bash
set -e

echo "=== Installing Dependencies for gemini-computer-use-agent ==="
python3 -m pip install --break-system-packages -r requirements.txt || python3 -m pip install -r requirements.txt

echo "=== Installing Playwright Chromium ==="
python3 -m playwright install chromium

echo "=== Setup Completed Successfully ==="
