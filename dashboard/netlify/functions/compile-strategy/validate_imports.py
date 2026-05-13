"""
Reads Python source from stdin, parses top-level imports with the ast module,
and checks each root module against SUPPORTED_PACKAGES.
Prints a JSON array of unknown module names to stdout.
Exits 0 always — warnings are surfaced to the caller, not treated as errors.
"""
import ast
import sys
import json

SUPPORTED_PACKAGES = {
    # Data / numerics
    'pandas', 'numpy', 'scipy', 'statsmodels', 'sklearn', 'math',
    'statistics', 'decimal', 'fractions', 'random',
    # Trading / broker
    'lumibot', 'alpaca_trade_api', 'alpaca', 'ta', 'ta_lib', 'talib',
    'yfinance', 'pytz', 'dateutil',
    # Standard library
    'datetime', 'time', 'calendar', 'os', 'sys', 'io', 'pathlib',
    'collections', 'itertools', 'functools', 'operator', 'copy',
    'typing', 'types', 'abc', 'enum', 'dataclasses',
    'json', 'csv', 're', 'struct', 'hashlib', 'uuid',
    'logging', 'warnings', 'traceback', 'inspect',
    'threading', 'queue', 'asyncio', 'concurrent',
    'urllib', 'http', 'requests',
    '__future__',
}

def get_root(module_name: str) -> str:
    """Return the top-level package name (e.g. 'pandas' from 'pandas.core.frame')."""
    return (module_name or '').split('.')[0]

def collect_imports(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # py_compile already caught this; return empty so we don't double-report
        return []

    unknown = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = get_root(alias.name)
                if root and root not in SUPPORTED_PACKAGES:
                    unknown.append(root)
        elif isinstance(node, ast.ImportFrom):
            root = get_root(node.module)
            if root and root not in SUPPORTED_PACKAGES:
                unknown.append(root)

    # Deduplicate, preserve order
    seen = set()
    deduped = []
    for name in unknown:
        if name not in seen:
            seen.add(name)
            deduped.append(name)
    return deduped

if __name__ == '__main__':
    source = sys.stdin.read()
    unknown = collect_imports(source)
    print(json.dumps(unknown))
