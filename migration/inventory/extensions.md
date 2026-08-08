# Extensions

    pg_cron                  1.6.4      schema=pg_catalog
    pg_partman               5.3.1      schema=partman
    pg_stat_statements       1.11       schema=extensions
    pgcrypto                 1.3        schema=extensions
    plpgsql                  1.0        schema=pg_catalog
    supabase_vault           0.3.1      schema=vault
    uuid-ossp                1.1        schema=extensions
    wrappers                 0.5.7      schema=extensions

## Verify against Cloud SQL (2)

    supabase_vault
    wrappers

These are Supabase/third-party extensions that Cloud SQL may not
offer. Confirm each against the current Cloud SQL supported list
before assuming the schema ports cleanly.
