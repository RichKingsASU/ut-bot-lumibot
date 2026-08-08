# Scheduled jobs (pg_cron)

    [2] 0 * * * *        partman-maintenance active=True
    [3] 30 11 * * 1-5    refresh-open-interest active=True
    [4] * * * * *        hitl_queue_expire_job active=True
