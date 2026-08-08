#!/usr/bin/env python3
"""
pg_inventory.py - Gate 0 deep PostgreSQL introspection.

The REST/PostgREST audit in supabase_audit.py can only see tables and columns.
Sequences, keys, indexes, triggers, functions, extensions, cron jobs and
publications require a direct Postgres connection. This closes that gap.

Strictly read-only: SELECTs against catalog views only. It never modifies
replication slots or publications, and never executes a cron job.

Usage:
    set -a && source .env && set +a
    ./venv/bin/python migration/pg_inventory.py
"""

import csv
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "migration" / "inventory"

# Schemas Supabase owns. Their functionality is replaced by GCP services, so
# they are NOT migration candidates -- reproducing them in Cloud SQL would
# recreate a platform we are leaving.
PLATFORM_SCHEMAS = {
    "auth", "storage", "realtime", "extensions", "graphql", "graphql_public",
    "vault", "supabase_functions", "supabase_migrations", "pgbouncer",
    "net", "cron", "pgsodium", "pgsodium_masks", "_realtime", "_analytics",
}
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}

Q = {
    "schemas": """
        SELECT nspname AS schema,
               pg_get_userbyid(nspowner) AS owner
        FROM pg_namespace
        WHERE nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast%'
        ORDER BY 1
    """,
    "tables": """
        SELECT n.nspname AS schema, c.relname AS name,
               CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view'
                              WHEN 'm' THEN 'matview' WHEN 'p' THEN 'partitioned'
                              WHEN 'f' THEN 'foreign' ELSE c.relkind::text END AS type,
               COALESCE(c.reltuples::bigint, 0) AS est_rows,
               c.relrowsecurity AS rls_enabled
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r','v','m','p','f')
          AND n.nspname NOT IN ('pg_catalog','information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'
        ORDER BY 1,2
    """,
    "sequences": """
        SELECT schemaname AS schema, sequencename AS name, data_type::text AS type
        FROM pg_sequences ORDER BY 1,2
    """,
    "constraints": """
        SELECT n.nspname AS schema, rel.relname AS table_name, con.conname AS name,
               CASE con.contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY'
                                WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK'
                                ELSE con.contype::text END AS type,
               pg_get_constraintdef(con.oid) AS definition
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema')
        ORDER BY 1,2,4
    """,
    "indexes": """
        SELECT schemaname AS schema, tablename AS table_name,
               indexname AS name, indexdef AS definition
        FROM pg_indexes
        WHERE schemaname NOT IN ('pg_catalog','information_schema')
        ORDER BY 1,2,3
    """,
    "triggers": """
        SELECT n.nspname AS schema, c.relname AS table_name, t.tgname AS name,
               pg_get_triggerdef(t.oid) AS definition
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT t.tgisinternal
          AND n.nspname NOT IN ('pg_catalog','information_schema')
        ORDER BY 1,2,3
    """,
    "functions": """
        SELECT n.nspname AS schema, p.proname AS name,
               pg_get_function_identity_arguments(p.oid) AS args,
               pg_get_function_result(p.oid) AS returns,
               l.lanname AS language, p.prosecdef AS security_definer
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_language l ON l.oid = p.prolang
        WHERE n.nspname NOT IN ('pg_catalog','information_schema')
        ORDER BY 1,2
    """,
    "extensions": """
        SELECT e.extname AS name, e.extversion AS version, n.nspname AS schema
        FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
        ORDER BY 1
    """,
    "publications": """
        SELECT pubname AS name, puballtables AS all_tables,
               pubinsert, pubupdate, pubdelete, pubtruncate
        FROM pg_publication ORDER BY 1
    """,
    "policies": """
        SELECT schemaname AS schema, tablename AS table_name, policyname AS name,
               roles::text AS roles, cmd, COALESCE(qual,'') AS using_expr
        FROM pg_policies ORDER BY 1,2,3
    """,
}

# Extensions Cloud SQL for PostgreSQL does not offer. Flagged, not assumed --
# the supported list changes, so treat these as "verify before migrating".
CLOUDSQL_SUSPECT = {
    "pg_graphql", "pgsodium", "supabase_vault", "pg_jsonschema", "pgjwt",
    "wrappers", "pg_net", "http", "index_advisor", "pg_tle", "vault",
}


def classify(schema: str) -> str:
    if schema in SYSTEM_SCHEMAS:
        return "SYSTEM"
    if schema in PLATFORM_SCHEMAS:
        return "SUPABASE_PLATFORM"
    return "APPLICATION"


def main() -> int:
    dsn = os.environ.get("SUPABASE_DSN")
    if not dsn:
        print("[FAIL] SUPABASE_DSN not set. Run: set -a && source .env && set +a")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    data = {}
    with psycopg2.connect(dsn, connect_timeout=30) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for key, sql in Q.items():
                try:
                    cur.execute(sql)
                    data[key] = [dict(r) for r in cur.fetchall()]
                except Exception as e:
                    # A missing catalog (e.g. no pg_cron) is information, not failure.
                    conn.rollback()
                    data[key] = []
                    print(f"  [WARN] {key}: {type(e).__name__}: {str(e)[:70]}")

            # pg_cron lives in its own schema and may not be installed.
            try:
                cur.execute("SELECT jobid, schedule, jobname, active FROM cron.job ORDER BY jobid")
                data["cron"] = [dict(r) for r in cur.fetchall()]
            except Exception:
                conn.rollback()
                data["cron"] = None  # distinct from "installed but empty"

    app = lambda rows: [r for r in rows if classify(r.get("schema", "")) == "APPLICATION"]

    # --- database-objects.csv : every object with its classification ---
    with (OUT / "database-objects.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["schema", "object", "type", "classification", "detail"])
        for r in data["tables"]:
            w.writerow([r["schema"], r["name"], r["type"], classify(r["schema"]),
                        f"est_rows={r['est_rows']};rls={r['rls_enabled']}"])
        for r in data["sequences"]:
            w.writerow([r["schema"], r["name"], "sequence", classify(r["schema"]), r["type"]])
        for r in data["constraints"]:
            w.writerow([r["schema"], r["name"], r["type"], classify(r["schema"]),
                        f"on={r['table_name']}"])
        for r in data["indexes"]:
            w.writerow([r["schema"], r["name"], "index", classify(r["schema"]),
                        f"on={r['table_name']}"])
        for r in data["triggers"]:
            w.writerow([r["schema"], r["name"], "trigger", classify(r["schema"]),
                        f"on={r['table_name']}"])
        for r in data["functions"]:
            w.writerow([r["schema"], r["name"], "function", classify(r["schema"]),
                        f"lang={r['language']};secdef={r['security_definer']}"])

    # --- extensions.md ---
    suspect = [e for e in data["extensions"] if e["name"] in CLOUDSQL_SUSPECT]
    (OUT / "extensions.md").write_text(
        "# Extensions\n\n" + "".join(
            f"    {e['name']:<24} {e['version']:<10} schema={e['schema']}\n"
            for e in data["extensions"])
        + f"\n## Verify against Cloud SQL ({len(suspect)})\n\n"
        + ("".join(f"    {e['name']}\n" for e in suspect) or "    (none)\n")
        + "\nThese are Supabase/third-party extensions that Cloud SQL may not\n"
          "offer. Confirm each against the current Cloud SQL supported list\n"
          "before assuming the schema ports cleanly.\n"
    )

    # --- cron.md ---
    if data["cron"] is None:
        cron_body = "pg_cron is **not installed**. No scheduled jobs to migrate.\n"
    elif not data["cron"]:
        cron_body = "pg_cron is installed but **no jobs are defined**.\n"
    else:
        cron_body = "".join(
            f"    [{c['jobid']}] {c['schedule']:<16} {c['jobname']} active={c['active']}\n"
            for c in data["cron"])
    (OUT / "cron.md").write_text("# Scheduled jobs (pg_cron)\n\n" + cron_body)

    # --- publications.md ---
    pubs = data["publications"]
    (OUT / "publications.md").write_text(
        "# Publications / logical replication\n\n"
        + ("".join(f"    {p['name']:<24} all_tables={p['all_tables']} "
                   f"i/u/d/t={p['pubinsert']}/{p['pubupdate']}/{p['pubdelete']}/{p['pubtruncate']}\n"
                   for p in pubs) or "    (none)\n")
        + "\nInspected only. No slot or publication was created, altered or dropped.\n"
        + ("\nA publication exists, so logical replication is feasible as a "
           "Cloud SQL migration path (Method B) rather than dump/restore only.\n"
           if pubs else
           "\nNo publications exist. Logical-replication CDC would require creating\n"
           "one; until then pg_dump baseline is the practical migration path.\n")
    )

    counts = {
        "schemas": len(data["schemas"]),
        "tables/views": len(data["tables"]),
        "  application": len(app(data["tables"])),
        "sequences": len(data["sequences"]),
        "primary keys": sum(1 for r in data["constraints"] if r["type"] == "PRIMARY KEY"),
        "foreign keys": sum(1 for r in data["constraints"] if r["type"] == "FOREIGN KEY"),
        "unique/check": sum(1 for r in data["constraints"] if r["type"] in ("UNIQUE", "CHECK")),
        "indexes": len(data["indexes"]),
        "triggers": len(data["triggers"]),
        "functions": len(data["functions"]),
        "  application": len(app(data["functions"])),
        "extensions": len(data["extensions"]),
        "  cloudsql-suspect": len(suspect),
        "policies": len(data["policies"]),
        "publications": len(pubs),
        "pg_cron jobs": "not installed" if data["cron"] is None else len(data["cron"]),
    }
    print("=== Gate 0 deep inventory ===")
    for k, v in counts.items():
        print(f"  {k:<22} {v}")
    print(f"\nwrote database-objects.csv, extensions.md, cron.md, publications.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
