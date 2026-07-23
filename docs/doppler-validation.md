# Doppler Validation Tests

Run these tests on the edge server to confirm Doppler is fully operational.

### 1. Test Doppler injects secrets correctly
```bash
doppler run --project disrupting-alpha --config production \
  -- python scripts/verify-doppler.py
```

### 2. Test Anthropic keys via Doppler
```bash
doppler run --project disrupting-alpha --config production \
  -- python scripts/verify_keys.py
```

### 3. Test a service starts with Doppler injection
```bash
sudo systemctl restart da-crypto.service
sleep 5
sudo systemctl status da-crypto.service
```

### 4. Confirm no .env needed
```bash
sudo mv /home/k2/ut-bot-lumibot/.env /tmp/.env.test
sudo systemctl restart da-crypto.service
sudo systemctl status da-crypto.service
```
*(If active → Doppler working. Restore with: `sudo mv /tmp/.env.test /home/k2/ut-bot-lumibot/.env`)*
