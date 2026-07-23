# Safe Removal of `.env` Checklist

Steps to safely remove `.env` from disk after Doppler is confirmed working:

- [ ] `doppler run -- python scripts/verify-doppler.py` → all PASS
- [ ] `sudo systemctl restart da-crypto da-trading da-agents da-watchdog da-hermes` → all active
- [ ] Telegram receives restart messages from Hermes
- [ ] `verify_keys.py` PASS via doppler run
- [ ] Dashboard loads at disruptingalpha.com
- [ ] Run: `mv .env .env.backup && chmod 000 .env.backup`
- [ ] Test restart of one service — confirm it reads from Doppler (`sudo systemctl restart da-crypto`)
- [ ] Only then: `rm .env.backup`
