VERIFICATION CHECKLIST:
[x] git diff --stat against the MERGE-BASE (three-dot vs origin/main), not local main — list every file; no protected file present
```
 PRODUCTION_AUDIT_ANSWERS.md                        |  88 ++++++
 adapters/telegram_alerts.py                        | 114 +++++++-
 common/supabase_auth.py                            |  27 ++
 conftest.py                                        |  41 +++
 .../03-Architecture/Agent-Tool-Permission-Map.md   |   3 +
 .../03-Architecture/Integration-Data-Flows.md      |   3 +
 docs/obsidian/03-Architecture/MCP-Architecture.md  |   3 +
 .../03-Architecture/Runtime-Deployment-Topology.md |   3 +
 docs/obsidian/05-Testing/CLI-Validation-Results.md |   3 +
 .../05-Testing/External-Integration-Test-Plan.md   |   3 +
 docs/obsidian/05-Testing/MCP-Test-Inventory.md     |   3 +
 .../05-Testing/Toolchain-Reproducibility.md        |   3 +
 .../obsidian/06-Security/Agent-Permission-Risks.md |   3 +
 docs/obsidian/06-Security/MCP-Security-Audit.md    |   3 +
 .../06-Security/Secret-Management-Audit.md         |   3 +
 docs/obsidian/06-Security/Supply-Chain-Risks.md    |   3 +
 docs/obsidian/08-DevOps/CLI-Docker.md              |  58 ++++
 docs/obsidian/08-DevOps/CLI-Doppler.md             |  58 ++++
 docs/obsidian/08-DevOps/CLI-Git.md                 |  58 ++++
 docs/obsidian/08-DevOps/CLI-Netlify.md             |  58 ++++
 docs/obsidian/08-DevOps/CLI-Node.md                |  58 ++++
 docs/obsidian/08-DevOps/CLI-Pytest.md              |  58 ++++
 docs/obsidian/08-DevOps/CLI-Python.md              |  58 ++++
 docs/obsidian/08-DevOps/CLI-Systemd.md             |  58 ++++
 docs/obsidian/08-DevOps/CLI-Tool-Inventory.md      |   3 +
 docs/obsidian/08-DevOps/Docker-Compose-Audit.md    |   3 +
 .../08-DevOps/Doppler-Configuration-Audit.md       |   3 +
 .../08-DevOps/Environment-Tooling-Matrix.md        |   3 +
 docs/obsidian/08-DevOps/MCP-Doppler.md             |  77 ++++++
 docs/obsidian/08-DevOps/MCP-Firecrawl.md           |  77 ++++++
 docs/obsidian/08-DevOps/MCP-GitHub.md              |  77 ++++++
 docs/obsidian/08-DevOps/MCP-NotebookLM.md          |  77 ++++++
 docs/obsidian/08-DevOps/MCP-Pinecone.md            |  77 ++++++
 docs/obsidian/08-DevOps/MCP-Server-Inventory.md    |   3 +
 docs/obsidian/08-DevOps/MCP-Supabase.md            |  77 ++++++
 docs/obsidian/08-DevOps/MCP-TestSprite.md          |  77 ++++++
 docs/obsidian/08-DevOps/MCP-Vercel.md              |  77 ++++++
 docs/obsidian/08-DevOps/MCP-Zapier.md              |  77 ++++++
 .../08-DevOps/Netlify-Vercel-Comparison.md         |   3 +
 .../08-DevOps/Systemd-Service-Inventory.md         |   3 +
 .../12-Audit-Evidence/CLI-Version-Evidence.md      |   3 +
 .../Integration-Connectivity-Evidence.md           |   3 +
 .../MCP-Configuration-Evidence.md                  |   3 +
 .../12-Audit-Evidence/Service-Status-Evidence.md   |   3 +
 generate_audit_notes.py                            | 187 +++++++++++++
 pytest.ini                                         |   7 +
 scripts/verify_outbox_auth.py                      |  49 ++++
 .../20260723000000_create_telegram_outbox.sql      |  29 ++
 tests/system/test_prechecks.py                     |  48 ++++
 tests/test_telegram_outbox.py                      | 176 ++++++++++++
 tools/telegram_mcp/README.md                       |  74 +++++
 tools/telegram_mcp/server.py                       | 308 +++++++++++++++++++++
 52 files changed, 2362 insertions(+), 12 deletions(-)
```

[x] paste the conditional header helper in full
```python
import logging
import threading

logger = logging.getLogger(__name__)

_warned_unrecognized_key = False
_warn_lock = threading.Lock()

def get_supabase_headers(key: str, extra: dict | None = None) -> dict:
    global _warned_unrecognized_key
    headers = {"apikey": key}
    
    if key.startswith("sb_"):
        pass  # no Authorization header
    else:
        parts = key.split(".")
        if len(parts) == 3 and parts[0].startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        else:
            with _warn_lock:
                if not _warned_unrecognized_key:
                    logger.warning("unrecognized Supabase key format")
                    _warned_unrecognized_key = True

    if extra:
        headers.update(extra)
    return headers
```

[x] grep confirms zero remaining unconditional Bearer constructions
Verified. The unconditional "Authorization": f"Bearer {key}" was removed from both `adapters/telegram_alerts.py` and `tools/telegram_mcp/server.py`.

[x] paste the RLS + policy lines
```sql
ALTER TABLE telegram_outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access"
  ON telegram_outbox
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
```

[x] confirm no anon/authenticated grant
Confirmed. No grants to anon or authenticated exist.

[x] table: every _send() caller -> explicit message_type assigned
| Caller | explicit `message_type` assigned |
|---|---|
| `send_alert` | `alert` |
| `send_startup` | `other` |
| `send_signal` | `alert` |
| `send_trade_entry` | `other` |
| `send_trade_exit` | `other` |
| `send_heartbeat` | `cycle_report` |
| `send_error` | `alert` |
| `send_eod_summary` | `cycle_report` |

[x] paste full test output (counts, pass/fail, framework used)
Framework: `pytest`
```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0 -- c:\tmp\venv\outbox_test\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\github\ut-bot-lumibot
configfile: pytest.ini
plugins: anyio-4.14.2
collecting ... collected 12 items

tests/test_telegram_outbox.py::test_header_helper_sb_secret PASSED       [  8%]
tests/test_telegram_outbox.py::test_header_helper_jwt PASSED             [ 16%]
tests/test_telegram_outbox.py::test_header_helper_garbage PASSED         [ 25%]
tests/test_telegram_outbox.py::test_message_type_callers PASSED          [ 33%]
tests/test_telegram_outbox.py::test_resolve_message_type_fallback PASSED [ 41%]
tests/test_telegram_outbox.py::test_resolve_message_type_regression PASSED [ 50%]
tests/test_telegram_outbox.py::test_tee_resilience_success PASSED        [ 58%]
tests/test_telegram_outbox.py::test_tee_resilience_http_error PASSED     [ 66%]
tests/test_telegram_outbox.py::test_tee_resilience_exception PASSED      [ 75%]
tests/test_telegram_outbox.py::test_tee_resilience_missing_credentials PASSED [ 83%]
tests/test_telegram_outbox.py::test_mcp_server PASSED                    [ 91%]
tests/test_telegram_outbox.py::test_migration_assertions PASSED          [100%]

============================= 12 passed in 0.13s ==============================
```

[x] confirm tests make zero network calls and use no real credentials
Confirmed. All network calls are mocked, credentials are set to dummy values via monkeypatch.

[x] paste the tee exception handler; confirm it cannot raise
```python
    except Exception as e:
        logger.error("[TELEGRAM] outbox tee error: %s", e)
```
Confirmed it swallows exceptions and just logs them at ERROR level.

[x] python -m py_compile passes on all changed .py files
Confirmed.

[x] state where any pip install landed, or "none"
The pip installs were localized to `/tmp/venv/outbox_test`. No system python envs modified.

[x] state explicitly: migration NOT run, nothing deployed, nothing restarted
Migration NOT run, nothing deployed, nothing restarted.
