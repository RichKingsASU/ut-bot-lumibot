# Database

35 tables/views via PostgREST; 23 migration files.

    agent_signals
    backtest_results
    bar_inventory
    bar_log
    bot_signals
    bot_status
    component_heartbeat
    component_status
    data_inventory
    greeks_snapshots
    hermes_news_feed
    hermes_observations
    hitl_gate
    hitl_queue
    kill_switch
    news_articles
    ohlcv_bars
    options_chain
    options_chain_summary
    options_inventory
    paper_trades
    portfolio_snapshots
    regime_states
    risk_config
    seed_jobs
    sessions
    signal_log
    signal_performance
    strategies
    system_alerts
    system_audit
    system_audits
    trade_log
    trade_performance
    user_settings

## RLS

60 policies across 23 tables.

    anon           6
    authenticated  26
    public         1
    service_role   27

**auth.uid() (per-row ownership) policies: 0**

Zero per-row ownership policies: RLS is coarse role gating and becomes
API middleware, not per-row policy translation.
