# Realtime — one hook, three tables

    dashboard/src/hooks/useSupabaseRealtime.ts
      channel('operator-console')
        postgres_changes -> agent_signals
        postgres_changes -> bot_status
        postgres_changes -> system_alerts

One channel, three subscriptions, one consumer. No presence, no broadcast.

## Recommendation

This is an operator console pushing status changes to a dashboard — it does
not need Pub/Sub plus a WebSocket gateway plus a Cloud Run fan-out tier. That
architecture costs more to build and run than the requirement justifies.

Options in increasing order of effort:

1. Poll these three tables from the Cloud Run API (simplest; the console is a
   single-operator surface, so refresh latency of a few seconds is acceptable)
2. SSE from Cloud Run, backed by Postgres `LISTEN/NOTIFY` on Cloud SQL
3. Full Pub/Sub -> WebSocket gateway (only if realtime consumers multiply)

The plan's own note applies here: much of "Realtime" usage is subscription
behaviour that simplifies away. Measured at three tables and one consumer, it
does.
