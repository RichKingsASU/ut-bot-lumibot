#!/usr/bin/env python3
"""
supabase_audit.py - Phase 0 Supabase -> GCP migration audit.

Regenerates migration/inventory/*.md from the live Supabase project plus a
scan of this repository. Safe to re-run: it is read-only against Supabase and
overwrites only files under migration/inventory/.

Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from the environment (source
.env first). Never prints or writes credential values -- only presence and
derived counts.

Usage:
    set -a && source .env && set +a
    ./venv/bin/python migration/supabase_audit.py
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "migration" / "inventory"

# Directories that are vendored, virtualenv, or build output. Counting these
# inflates every metric -- an early run reported 51k Python files.
PRUNE = [
    "node_modules", "venv", ".venv", "venv_broken_py314", "test_venv",
    "node-local", "__pycache__", ".git", "site-packages", "dist", "build",
]

# The Supabase surfaces we care about, as (label, regex).
SURFACES = [
    ("createClient",        r"createClient"),
    ("auth",                r"\.auth\."),
    ("storage",             r"\.storage\.|storage\.from\("),
    ("realtime",            r"\.channel\(|postgres_changes"),
    ("rpc",                 r"\.rpc\("),
    ("supabase-py",         r"from supabase import|import supabase"),
    ("psycopg2",            r"psycopg2"),
]


def api(path: str, default=None):
    """GET against the Supabase project. Returns `default` on any failure."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        return default
    req = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] {path}: {type(e).__name__}", file=sys.stderr)
        return default


def grep_files(pattern: str) -> list:
    """Files matching `pattern`, excluding vendored trees. [] if ripgrep/grep finds none."""
    cmd = ["grep", "-rlE", pattern, str(REPO)]
    cmd += [f"--exclude-dir={d}" for d in PRUNE]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return [l for l in res.stdout.splitlines() if l.strip()]


def audit_database() -> dict:
    spec = api("/rest/v1/", {}) or {}
    tables = sorted((spec.get("definitions") or {}).keys())

    migrations = sorted((REPO / "supabase" / "migrations").glob("*.sql"))
    sql = "\n".join(p.read_text(errors="replace") for p in migrations)

    policies = re.findall(r'CREATE POLICY\s+"([^"]+)"\s+ON\s+(\w+)', sql, re.I)
    roles = re.findall(r"\bTO\s+(service_role|authenticated|anon|public)\b", sql, re.I)
    # auth.uid() means per-row ownership; auth.role() is coarse role gating.
    # The distinction decides whether RLS becomes API middleware or per-row logic.
    uid_policies = re.findall(r"auth\.uid\(\)", sql)

    return {
        "tables": tables,
        "migrations": len(migrations),
        "policies": policies,
        "rls_tables": sorted({t for _, t in policies}),
        "roles": {r: roles.count(r) for r in sorted(set(roles))},
        "uid_policy_count": len(uid_policies),
    }


def audit_auth() -> dict:
    data = api("/auth/v1/admin/users?per_page=200", {}) or {}
    users = data.get("users", data if isinstance(data, list) else [])
    providers, mfa = set(), 0
    for u in users:
        for ident in (u.get("identities") or []):
            if ident.get("provider"):
                providers.add(ident["provider"])
        # identities[] can be absent on the admin list endpoint; app_metadata
        # still carries the provider, so fall back to it rather than reporting
        # "no providers" for a user that plainly has one.
        fallback = (u.get("app_metadata") or {}).get("provider")
        if fallback:
            providers.add(fallback)
        if u.get("factors"):
            mfa += 1
    calls = re.findall(r"\.auth\.([a-zA-Z]+)", "\n".join(
        Path(f).read_text(errors="replace") for f in grep_files(r"\.auth\.")))
    return {
        "count": len(users),
        "providers": sorted(providers),
        "mfa": mfa,
        "calls": {c: calls.count(c) for c in sorted(set(calls))},
    }


def audit_storage() -> dict:
    buckets = api("/storage/v1/bucket", []) or []
    return {"buckets": buckets, "code_refs": len(grep_files(r"\.storage\.|storage\.from\("))}


def audit_functions() -> dict:
    netlify = sorted((REPO / "dashboard" / "netlify" / "functions").glob("*.ts"))
    return {
        "supabase_edge": (REPO / "supabase" / "functions").is_dir(),
        "netlify": [p.name for p in netlify],
    }


def main() -> int:
    if not os.environ.get("SUPABASE_URL"):
        print("[FAIL] SUPABASE_URL not set. Run: set -a && source .env && set +a")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    db, auth, storage, fns = audit_database(), audit_auth(), audit_storage(), audit_functions()
    surfaces = {label: len(grep_files(pat)) for label, pat in SURFACES}

    (OUT / "database.md").write_text(
        f"# Database\n\n{len(db['tables'])} tables/views via PostgREST; "
        f"{db['migrations']} migration files.\n\n"
        + "".join(f"    {t}\n" for t in db["tables"])
        + f"\n## RLS\n\n{len(db['policies'])} policies across "
          f"{len(db['rls_tables'])} tables.\n\n"
        + "".join(f"    {r:<14} {n}\n" for r, n in db["roles"].items())
        + f"\n**auth.uid() (per-row ownership) policies: {db['uid_policy_count']}**\n"
        + ("\nZero per-row ownership policies: RLS is coarse role gating and becomes\n"
           "API middleware, not per-row policy translation.\n"
           if db["uid_policy_count"] == 0 else
           "\nPer-row ownership policies exist and need individual translation.\n")
    )

    (OUT / "auth.md").write_text(
        f"# Auth\n\nusers: {auth['count']}\nproviders: "
        f"{', '.join(auth['providers']) or '(none)'}\nMFA enrolled: {auth['mfa']}\n\n"
        "## Call sites\n\n"
        + "".join(f"    .auth.{c:<22} x{n}\n" for c, n in auth["calls"].items())
    )

    (OUT / "storage.md").write_text(
        f"# Storage\n\nbuckets: {len(storage['buckets'])}\n"
        f"code references: {storage['code_refs']}\n\n"
        + ("**NOT APPLICABLE** - nothing to migrate; drop the storage phase.\n"
           if not storage["buckets"] and not storage["code_refs"]
           else "Storage is in use; migration required.\n")
    )

    (OUT / "functions.md").write_text(
        f"# Serverless\n\nsupabase/functions/: "
        f"{'present' if fns['supabase_edge'] else 'ABSENT'}\n"
        f"netlify functions: {len(fns['netlify'])}\n\n"
        + "".join(f"    {n}\n" for n in fns["netlify"])
        + ("\nNo Supabase Edge Functions exist. The serverless tier is Netlify -\n"
           "a separate vendor migration, not Supabase Edge -> Cloud Run.\n"
           if not fns["supabase_edge"] else "")
    )

    (OUT / "application-dependencies.md").write_text(
        "# Application coupling\n\n(files matching each surface)\n\n"
        + "".join(f"    {k:<16} {v}\n" for k, v in surfaces.items())
    )

    print("=== Phase 0 audit ===")
    print(f"  tables            {len(db['tables'])}")
    print(f"  RLS policies      {len(db['policies'])} over {len(db['rls_tables'])} tables")
    print(f"  auth.uid policies {db['uid_policy_count']}")
    print(f"  auth users        {auth['count']} ({', '.join(auth['providers']) or 'none'})")
    print(f"  storage buckets   {len(storage['buckets'])}")
    print(f"  netlify functions {len(fns['netlify'])}")
    print(f"  supabase edge fns {'present' if fns['supabase_edge'] else 'ABSENT'}")
    print(f"\nwrote {len(list(OUT.glob('*.md')))} files to {OUT.relative_to(REPO)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
