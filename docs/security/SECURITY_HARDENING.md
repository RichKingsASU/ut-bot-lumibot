# Security Hardening Review

`manage.py check` and `check --deploy` were attempted only after dependency installation, which was blocked by the package registry; they are not claimed as passing. Production settings fail closed on missing/short secret key, missing/non-PostgreSQL database URL, disable DEBUG, require explicit hosts, HTTPS redirect, secure/HTTP-only/SameSite session cookies, secure/HTTP-only CSRF cookie, one-year HSTS with preload/subdomains, content-type protection, same-origin referrer, and frame denial.

| Severity | Finding | Status |
|---|---|---|
| P0 | Tests and PG17 schema not executable on this host | OPEN |
| P0 | Restore drill absent | OPEN |
| P1 | MFA/provisioning/deprovisioning not validated | OPEN |
| P1 | Legacy secrets incident rotation not externally attested | OPEN |
| P1 | Dependency vulnerability and image scans absent | OPEN |
| P1 | HTTPS/reverse proxy not staged | OPEN |
| P2 | CSP and rate limiting not yet defined | OPEN |
| P2 | Managed log sink/redaction drill absent | OPEN |
