# telegram_outbox MCP server (read-only)

A local **stdio** MCP server that exposes the Supabase `telegram_outbox` audit
table over three **read-only** tools. It never writes, never sends a Telegram
message, and never calls the Telegram API.

## Tools

| Tool | Arguments | Returns |
| --- | --- | --- |
| `get_recent_reports` | `limit: int = 10`, `message_type: str \| None` | Most recent outbox rows, newest first (optionally filtered by `message_type`). |
| `get_reports_since` | `iso_timestamp: str` | Rows with `sent_at >= iso_timestamp`, newest first. |
| `get_outbox_health` | — | `newest_sent_at`, `age_seconds`, `count_24h`, `failed_send_count_24h`. |

## Requirements

- Python 3.10+
- `httpx` (already a project dependency)
- Environment:
  - `SUPABASE_URL`
  - **one of** `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY`
    (either is accepted while the key naming migration is in progress)

The key is read from the environment only. It is never hardcoded, logged, or
echoed by the server.

## Claude Code MCP registration

Register the server with Claude Code using the CLI (run from the repo root).
Fill in your own values — do **not** commit real credentials:

```bash
claude mcp add-json telegram-outbox '{
  "command": "python3",
  "args": ["tools/telegram_mcp/server.py"],
  "env": {
    "SUPABASE_URL": "https://your-project.supabase.co",
    "SUPABASE_SECRET_KEY": "<your-supabase-service-key>"
  }
}'
```

Equivalent `.mcp.json` block (project scope):

```json
{
  "mcpServers": {
    "telegram-outbox": {
      "command": "python3",
      "args": ["tools/telegram_mcp/server.py"],
      "env": {
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_SECRET_KEY": "<your-supabase-service-key>"
      }
    }
  }
}
```

> This server is intentionally **not** registered anywhere by this change.
> Registration is left to the operator. Do not add it to any Antigravity /
> Gemini MCP config.

## Manual smoke test

List the exposed tools over stdio without any registration:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | SUPABASE_URL="$SUPABASE_URL" SUPABASE_SECRET_KEY="$SUPABASE_SECRET_KEY" \
    python3 tools/telegram_mcp/server.py
```
