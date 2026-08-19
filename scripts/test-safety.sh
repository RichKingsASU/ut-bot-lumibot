#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q \
  tests/test_execution_lease.py \
  tests/test_broker_reconciliation.py \
  tests/test_kill_flatten.py \
  tests/test_data_validity.py \
  tests/test_market_gap.py \
  tests/test_component_health.py \
  tests/test_watchdog_health.py
