#!/usr/bin/env python3
"""
Disrupting Alpha — Repo Audit Manifest Generator
Run from the repo root: python generate_manifest.py
Outputs: manifest_frontend.json, manifest_backend.json, manifest_summary.txt
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(os.getcwd())
FRONTEND_DIRS = ["src"]
BACKEND_DIRS  = ["strategies", "scripts", "signal_engine", "."]
BACKEND_EXTS  = {".py"}
FRONTEND_EXTS = {".tsx", ".ts", ".jsx", ".js"}
SKIP_DIRS     = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage"
}

PROTECTED_FILES = {
    "strategies/ut_bot.py",
    "strategies/options_executor.py",
    "k2_atr_strategy.py",
    "utbot_paper_trader.py",
}

RE_REACT_COMPONENT  = re.compile(r'(?:export\s+(?:default\s+)?(?:function|const|class)\s+(\w+)|export\s+default\s+(\w+))')
RE_NAMED_EXPORT     = re.compile(r'export\s+(?:const|function|class|type|interface|enum)\s+(\w+)')
RE_ROUTER_ROUTE     = re.compile(r'<Route[^>]+path=["\']([^"\']+)["\']')
RE_REACT_ROUTER_V6  = re.compile(r'path:\s*["\']([^"\']+)["\']')
RE_FETCH_URL        = re.compile(r'fetch\(["\`]([^"\'`\)]+)["\`]')
RE_AXIOS_URL        = re.compile(r'axios\.(?:get|post|put|patch|delete)\(["\`]([^"\'`\)]+)["\`]')
RE_SUPABASE_TABLE   = re.compile(r'supabase\.from\(["\'](\w+)["\']')
RE_VITE_ENV         = re.compile(r'import\.meta\.env\.(VITE_\w+)')
RE_PROCESS_ENV      = re.compile(r'process\.env\.(\w+)')
RE_IMPORT_FROM      = re.compile(r'from\s+["\']([^"\']+)["\']')
RE_PY_CLASS         = re.compile(r'^class\s+(\w+)', re.MULTILINE)
RE_PY_FUNCTION      = re.compile(r'^def\s+(\w+)', re.MULTILINE)
RE_PY_IMPORT        = re.compile(r'^(?:import|from)\s+([\w\.]+)', re.MULTILINE)
RE_PY_NATS_SUBJECT  = re.compile(r'["\']([a-z]+\.[a-z\.]+)["\']')
RE_PY_SUPABASE      = re.compile(r'\.table\(["\'](\w+)["\']|from_\(["\'](\w+)["\']')
RE_PY_TELEGRAM      = re.compile(r'bot\.send|send_message|sendMessage')
RE_PY_ENV           = re.compile(r'os\.(?:environ|getenv)\(["\'](\w+)["\']')
RE_PY_QUESTDB       = re.compile(r'INSERT INTO\s+(\w+)|SELECT .+ FROM\s+(\w+)', re.IGNORECASE)
RE_PY_QDRANT        = re.compile(r'collection_name=["\'](\w+)["\']')
RE_PY_LUMIBOT       = re.compile(r'class\s+\w+\s*\(\s*Strategy\s*\)')

def walk_files(root, dirs, exts):
    results = []
    for d in dirs:
        base = root / d
        if not base.exists():
            continue
        if base.is_file() and base.suffix in exts:
            results.append(base)
            continue
        for path in base.rglob("*"):
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            if path.suffix in exts and path.is_file():
                results.append(path)
    return sorted(set(results))

def read_file(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def rel(path):
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)

def analyze_frontend_file(path):
    src = read_file(path)
    r = rel(path)
    components   = RE_REACT_COMPONENT.findall(src)
    named        = RE_NAMED_EXPORT.findall(src)
    routes_v5    = RE_ROUTER_ROUTE.findall(src)
    routes_v6    = RE_REACT_ROUTER_V6.findall(src)
    fetches      = RE_FETCH_URL.findall(src)
    axios_calls  = RE_AXIOS_URL.findall(src)
    supa_tables  = RE_SUPABASE_TABLE.findall(src)
    vite_envs    = RE_VITE_ENV.findall(src)
    proc_envs    = RE_PROCESS_ENV.findall(src)
    imports      = RE_IMPORT_FROM.findall(src)
    comp_names   = [c[0] or c[1] for c in components if c[0] or c[1]]
    role = "unknown"
    if "/pages/" in r or "/views/" in r: role = "page"
    elif "/components/" in r: role = "component"
    elif "/hooks/" in r: role = "hook"
    elif "/utils/" in r or "/lib/" in r or "/helpers/" in r: role = "utility"
    elif "/store/" in r or "/context/" in r or "/state/" in r: role = "state"
    elif "/api/" in r or "/services/" in r: role = "api-service"
    elif "/types/" in r: role = "types"
    elif "App.tsx" in r or "main.tsx" in r: role = "entry"
    elif "router" in r.lower() or "routes" in r.lower(): role = "router"
    return {
        "file": r, "role": role, "components": comp_names,
        "named_exports": named, "routes": list(set(routes_v5 + routes_v6)),
        "api_calls": list(set(fetches + axios_calls)),
        "supabase_tables": list(set(supa_tables)),
        "env_vars": list(set(vite_envs + proc_envs)),
        "imports": imports, "line_count": src.count("\n"),
    }

def analyze_backend_file(path):
    src = read_file(path)
    r = rel(path)
    classes    = RE_PY_CLASS.findall(src)
    functions  = RE_PY_FUNCTION.findall(src)
    imports    = RE_PY_IMPORT.findall(src)
    env_vars   = RE_PY_ENV.findall(src)
    supa_hits  = RE_PY_SUPABASE.findall(src)
    supa_tables = list(set([t for pair in supa_hits for t in pair if t]))
    nats_subjs = RE_PY_NATS_SUBJECT.findall(src)
    questdb    = RE_PY_QUESTDB.findall(src)
    qdrant     = RE_PY_QDRANT.findall(src)
    is_lumibot = bool(RE_PY_LUMIBOT.search(src))
    has_telegram = bool(RE_PY_TELEGRAM.search(src))
    role = "unknown"
    if is_lumibot: role = "lumibot-strategy"
    elif "langgraph" in src or "StateGraph" in src: role = "langgraph-agent"
    elif "nats" in src.lower(): role = "nats-worker"
    elif "questdb" in src.lower() or "INSERT INTO" in src: role = "questdb-writer"
    elif "qdrant" in src.lower(): role = "qdrant-worker"
    elif "finbert" in src.lower() or "sentiment" in r.lower(): role = "sentiment"
    elif "hmm" in src.lower() or "regime" in r.lower(): role = "regime-detection"
    elif "greeks" in r.lower() or "mibian" in src.lower(): role = "greeks-engine"
    elif "kelly" in r.lower(): role = "position-sizing"
    elif "telegram" in r.lower() or has_telegram: role = "telegram-bot"
    elif r.startswith("scripts/"): role = "script"
    elif r.startswith("signal_engine/"): role = "signal-engine"
    protected = any(r.endswith(p) or r == p for p in PROTECTED_FILES)
    questdb_tables = list(set([t for pair in questdb for t in pair if t]))
    nats_subjects  = [s for s in nats_subjs if s.count(".") >= 1 and len(s) > 4]
    return {
        "file": r, "role": role, "protected": protected,
        "is_lumibot_strategy": is_lumibot, "has_telegram": has_telegram,
        "classes": classes, "functions": functions[:40], "imports": imports,
        "env_vars": list(set(env_vars)), "supabase_tables": list(set(supa_tables)),
        "nats_subjects": list(set(nats_subjects)),
        "questdb_tables": list(set(questdb_tables)),
        "qdrant_collections": list(set(qdrant)), "line_count": src.count("\n"),
    }

def summarize_frontend(files):
    all_routes, all_api_calls, all_supa_tables, all_env_vars, all_components = [], [], [], [], []
    roles = {}
    for f in files:
        all_routes += f["routes"]; all_api_calls += f["api_calls"]
        all_supa_tables += f["supabase_tables"]; all_env_vars += f["env_vars"]
        all_components += f["components"]; roles[f["role"]] = roles.get(f["role"], 0) + 1
    return {
        "total_files": len(files), "files_by_role": roles,
        "unique_routes": sorted(set(all_routes)),
        "unique_api_calls": sorted(set(all_api_calls)),
        "unique_supabase_tables": sorted(set(all_supa_tables)),
        "unique_env_vars": sorted(set(all_env_vars)),
        "unique_components": sorted(set(all_components)),
    }

def summarize_backend(files):
    all_env_vars, all_supa, all_nats, all_questdb, all_qdrant = [], [], [], [], []
    roles = {}; lumibot_strats = []; protected_files = []
    for f in files:
        all_env_vars += f["env_vars"]; all_supa += f["supabase_tables"]
        all_nats += f["nats_subjects"]; all_questdb += f["questdb_tables"]
        all_qdrant += f["qdrant_collections"]; roles[f["role"]] = roles.get(f["role"], 0) + 1
        if f["is_lumibot_strategy"]: lumibot_strats.append(f["file"])
        if f["protected"]: protected_files.append(f["file"])
    return {
        "total_files": len(files), "files_by_role": roles,
        "lumibot_strategies": lumibot_strats, "protected_files": protected_files,
        "unique_env_vars": sorted(set(all_env_vars)),
        "unique_supabase_tables": sorted(set(all_supa)),
        "unique_nats_subjects": sorted(set(all_nats)),
        "unique_questdb_tables": sorted(set(all_questdb)),
        "unique_qdrant_collections": sorted(set(all_qdrant)),
    }

def cross_reference(fe_summary, be_summary):
    fe_tables = set(fe_summary["unique_supabase_tables"])
    be_tables = set(be_summary["unique_supabase_tables"])
    fe_env    = set(fe_summary["unique_env_vars"])
    be_env    = set(be_summary["unique_env_vars"])
    return {
        "supabase_tables": {
            "frontend_only": sorted(fe_tables - be_tables),
            "backend_only":  sorted(be_tables - fe_tables),
            "shared":        sorted(fe_tables & be_tables),
        },
        "env_vars": {
            "frontend_only": sorted(fe_env - be_env),
            "backend_only":  sorted(be_env - fe_env),
            "shared":        sorted(fe_env & be_env),
        },
    }

def main():
    print(f"Scanning repo at: {REPO_ROOT}")
    print(f"Generated: {datetime.now().isoformat()}\n")
    fe_paths = walk_files(REPO_ROOT, FRONTEND_DIRS, FRONTEND_EXTS)
    print(f"Frontend files found: {len(fe_paths)}")
    fe_files = [analyze_frontend_file(p) for p in fe_paths]
    fe_summary = summarize_frontend(fe_files)
    be_paths = walk_files(REPO_ROOT, BACKEND_DIRS, BACKEND_EXTS)
    be_paths = [p for p in be_paths if not str(rel(p)).startswith("src/")]
    print(f"Backend files found:  {len(be_paths)}")
    be_files = [analyze_backend_file(p) for p in be_paths]
    be_summary = summarize_backend(be_files)
    xref = cross_reference(fe_summary, be_summary)
    out_fe = {"generated_at": datetime.now().isoformat(), "repo_root": str(REPO_ROOT), "summary": fe_summary, "files": fe_files}
    out_be = {"generated_at": datetime.now().isoformat(), "repo_root": str(REPO_ROOT), "summary": be_summary, "cross_reference": xref, "files": be_files}
    Path("manifest_frontend.json").write_text(json.dumps(out_fe, indent=2))
    Path("manifest_backend.json").write_text(json.dumps(out_be, indent=2))
    lines = [
        "=" * 70,
        "DISRUPTING ALPHA — REPO AUDIT MANIFEST SUMMARY",
        f"Generated: {datetime.now().isoformat()}",
        f"Repo root: {REPO_ROOT}",
        "=" * 70,
        "",
        "── FRONTEND ──────────────────────────────────────────────────────────",
        f"Total files:        {fe_summary['total_files']}",
        f"Files by role:      {fe_summary['files_by_role']}",
        f"Unique routes:      {fe_summary['unique_routes']}",
        f"Unique components:  {fe_summary['unique_components']}",
        f"API calls:          {fe_summary['unique_api_calls']}",
        f"Supabase tables:    {fe_summary['unique_supabase_tables']}",
        f"Env vars:           {fe_summary['unique_env_vars']}",
        "",
        "── BACKEND ───────────────────────────────────────────────────────────",
        f"Total files:        {be_summary['total_files']}",
        f"Files by role:      {be_summary['files_by_role']}",
        f"Lumibot strategies: {be_summary['lumibot_strategies']}",
        f"Protected files:    {be_summary['protected_files']}",
        f"Supabase tables:    {be_summary['unique_supabase_tables']}",
        f"NATS subjects:      {be_summary['unique_nats_subjects']}",
        f"QuestDB tables:     {be_summary['unique_questdb_tables']}",
        f"Qdrant collections: {be_summary['unique_qdrant_collections']}",
        f"Env vars:           {be_summary['unique_env_vars']}",
        "",
        "── CROSS-REFERENCE ───────────────────────────────────────────────────",
        "Supabase tables — frontend only: " + str(xref["supabase_tables"]["frontend_only"]),
        "Supabase tables — backend only:  " + str(xref["supabase_tables"]["backend_only"]),
        "Supabase tables — shared:        " + str(xref["supabase_tables"]["shared"]),
        "",
        "Env vars — frontend only:        " + str(xref["env_vars"]["frontend_only"]),
        "Env vars — backend only:         " + str(xref["env_vars"]["backend_only"]),
        "Env vars — shared:               " + str(xref["env_vars"]["shared"]),
        "=" * 70,
    ]
    summary_text = "\n".join(lines)
    Path("manifest_summary.txt").write_text(summary_text)
    print("\n✅ manifest_frontend.json written")
    print("✅ manifest_backend.json written")
    print("✅ manifest_summary.txt written\n")
    print(summary_text)

if __name__ == "__main__":
    main()
