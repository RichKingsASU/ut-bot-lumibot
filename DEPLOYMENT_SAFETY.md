# PRODUCTION DEPLOYMENT & SAFETY GUIDE

## 1. Pre-Deployment Checklist
- [ ] **Lint Check**: `flake8 .` (Python) and `npm run lint` (Frontend).
- [ ] **Type Check**: `mypy .` (Python).
- [ ] **Unit Tests**: `pytest`.
- [ ] **Env Validation**: Verify `ALPACA_IS_PAPER` is set correctly.
- [ ] **Secret Scan**: Ensure no keys are committed to Git.
- [ ] **Docker Config**: Run `docker-compose config` to verify YAML.

## 2. Deployment Steps
1. **Pull Latest Code**: `git pull origin main`.
2. **Build Stack**: `docker-compose build --no-cache`.
3. **Launch**: `docker-compose up -d`.
4. **Health Check**: `curl http://localhost:8000/ready`.
5. **Log Watch**: `docker-compose logs -f trading-bot`.

## 3. Trading Safety Rules
- **Rule 1**: Never enable LIVE trading on a Friday afternoon.
- **Rule 2**: Always verify the `MAX_DAILY_LOSS` is appropriate for the account size.
- **Rule 3**: The bot must have `sync_state_with_broker` success on every startup.
- **Rule 4**: Monitor the first 3 trades of every new version deployment manually.

## 4. Maintenance
- **Weekly**: Rotate `ADMIN_API_KEY`.
- **Monthly**: Review `MAX_DAILY_LOSS` and strategy performance.
- **On Broker Outage**: Stop the bot and clear `open_position` state manually if needed.
