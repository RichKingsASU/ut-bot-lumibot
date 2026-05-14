module.exports = {
  apps : [{
    name: "ut-bot-lumibot",
    script: "python",
    args: "main.py",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      NODE_ENV: "production",
    },
    error_file: "logs/err.log",
    out_file: "logs/out.log",
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    merge_logs: true
  }]
}
