#!/usr/bin/env python3
"""Validate the documented test interpreter and direct dependencies; never installs."""
from importlib.util import find_spec
import platform
import sys

REQUIRED = {
    "numpy": "numpy", "pandas": "pandas", "pydantic": "pydantic",
    "python-dotenv": "dotenv", "httpx": "httpx", "requests": "requests",
    "pytz": "pytz", "python-dateutil": "dateutil",
    "pandas-market-calendars": "pandas_market_calendars", "pytest": "pytest",
}
print(f"Python: {platform.python_version()}")
print(f"Platform: {platform.platform()} ({platform.machine()})")
if sys.version_info[:2] != (3, 11):
    raise SystemExit("ERROR: supported test interpreter is Python 3.11.x")
missing = [distribution for distribution, module in REQUIRED.items() if find_spec(module) is None]
if missing:
    raise SystemExit("ERROR: missing packages: " + ", ".join(missing))
print("Environment precheck: PASS")
