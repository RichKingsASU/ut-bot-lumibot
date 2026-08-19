#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/check_test_environment.py
python -m compileall -q src strategies agents collectors backtests scripts
python -m pytest --collect-only -q
scripts/test-safety.sh
python -m pytest -q backtests/tests/
python -m pytest -q
