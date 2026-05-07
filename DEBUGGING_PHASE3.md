# Debugging Guide — Phase 3

## Common issues

### 1. "no such table: audit_logs" on existing DB

The Phase 3 migration adds three new tables. If you have an existing `trady.db` from Phase 2, restart the server — `init_db()` on startup calls `create_all` which adds the missing tables.

If using Docker with a volume mount, ensure the container restarts:
```bash
docker compose down && docker compose up --build
```

### 2. "Bot unavailable: timed out" (HTTP 503)

In `TRADING_BOT_MODE=real`, the backend cannot reach the bot API.

- Check `TRADING_BOT_BASE_URL` is correct and reachable from the server
- Increase `TRADING_BOT_TIMEOUT_SECONDS` temporarily for debugging
- Switch to `TRADING_BOT_MODE=mock` to verify backend is healthy

### 3. Webhook returns 401 "Invalid webhook signature"

- Verify `TRADING_BOT_WEBHOOK_SECRET` matches on both sides
- Ensure the signature covers exactly: `TIMESTAMP\n<body>` (UTF-8, no trailing newline after body)
- Check `X-Trady-Timestamp` header is an integer Unix epoch seconds string

### 4. Webhook returns 400 "Webhook event is stale"

The bot's clock differs from the server by more than `WEBHOOK_MAX_AGE_SECONDS` (60s default).
- Sync NTP on the bot server
- Increase `WEBHOOK_MAX_AGE_SECONDS` for testing (not recommended for production)

### 5. "Approval not found" on POST /v1/trading/approve

- `approvalId` must be a UUID string returned by the command endpoint
- Approvals expire after `APPROVAL_TTL_SECONDS` (default 300s)
- Each approval is single-use — re-submitting after a decision returns 400

### 6. "Not your approval" error

The device ID that calls `/approve` must match the device ID that called `/command`. Use the same auth token.

### 7. Command returns 403 "Command is permanently blocked"

The command is in the always-blocked set. This cannot be overridden by config. The blocked set is hardcoded in `policy_engine.py`:
```
withdraw_funds, transfer_funds, reveal_api_keys, disable_all_safety, set_unlimited_leverage
```

### 8. Command returns 400 "Unknown command"

The command is not in any policy tier. Add it to `TRADING_BOT_ALLOWED_COMMANDS` or `TRADING_BOT_REQUIRE_APPROVAL_COMMANDS` in `.env`.

---

## AWS Lightsail deployment — Phase 3 steps

### 1. SSH into the instance
```bash
ssh -i your-key.pem ubuntu@<LIGHTSAIL_IP>
cd /home/ubuntu/trady-brain
```

### 2. Pull latest changes
```bash
git pull origin master
```

### 3. Set Phase 3 env vars

Edit `/home/ubuntu/trady-brain/.env` and add:
```
TRADING_BOT_MODE=mock
TRADING_BOT_HMAC_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">
TRADING_BOT_WEBHOOK_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">
APPROVAL_TTL_SECONDS=300
WEBHOOK_MAX_AGE_SECONDS=60
```

### 4. Rebuild and restart Docker
```bash
docker compose down
docker compose up --build -d
docker compose logs -f
```

### 5. Verify new endpoints
```bash
curl http://localhost:8000/health
curl http://localhost:8000/v1/trading/health \
  -H "Authorization: Bearer <token>"
```

### 6. Configure reverse proxy (if using nginx)

No new routes — the existing `location /` block covers all endpoints.

---

## Test the full approval flow manually

```bash
# 1. Auth
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/device \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"test","deviceName":"Test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# 2. Issue risky command
RESP=$(curl -s -X POST http://localhost:8000/v1/trading/command \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"command":"resume_bot","reason":"manual test","mode":"paper"}')
echo $RESP

APPROVAL_ID=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['approvalId'])")

# 3. Approve
curl -s -X POST http://localhost:8000/v1/trading/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"approvalId\":\"$APPROVAL_ID\",\"decision\":\"approve\",\"userConfirmationText\":\"I approve\"}"

# 4. Check audit
curl -s http://localhost:8000/v1/trading/audit \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Test webhook locally

```python
import hashlib, hmac, json, time, requests

secret = "trady-webhook-secret-CHANGE-IN-PRODUCTION"
body = json.dumps({"type": "drawdown_alert", "value": 5.2}).encode()
ts = str(int(time.time()))
sig = hmac.new(secret.encode(), ts.encode() + b"\n" + body, digestmod=hashlib.sha256).hexdigest()

r = requests.post(
    "http://localhost:8000/v1/trading/events/webhook",
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Trady-Timestamp": ts,
        "X-Trady-Signature": sig,
    }
)
print(r.json())
```

---

## Switching from mock to real bot

1. Set `TRADING_BOT_MODE=real` in `.env`
2. Set `TRADING_BOT_BASE_URL=https://your-bot-api.example.com`
3. Set `TRADING_BOT_API_KEY=<your-key>`
4. Set `TRADING_BOT_HMAC_SECRET=<shared-secret-with-bot>`
5. Ensure the bot API implements the expected endpoints:
   - `GET /bot/v1/health`
   - `GET /bot/v1/status`
   - `GET /bot/v1/metrics`
   - `GET /bot/v1/positions`
   - `GET /bot/v1/logs`
   - `POST /bot/v1/command`
6. Ensure the bot verifies incoming HMAC headers:
   - `X-Trady-Timestamp`
   - `X-Trady-Nonce`
   - `X-Trady-Signature`
7. Test with `pause_bot` first (lowest risk allowed command)
8. Test approval flow with `resume_bot` before enabling other approval commands
