# trady-brain

FastAPI backend for the Trady AI Voice Assistant — Phase 3.

## Safety notice

Trady is a **supervisor/control layer only**. It does NOT connect to any exchange, does NOT place real trades, and does NOT hold real funds. Real trading bot integration is proxied through a controlled supervisor channel with a strict policy engine. Mock mode is the default.

---

## Quick start (local)

```bash
cd trady-brain
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # edit secrets before deploying
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: http://localhost:8000/docs

---

## Quick start (Docker)

```bash
docker compose up --build
```

---

## Phase 3 — Trading Bot Supervisor

### Architecture

```
Android App
    ↓ JWT Bearer
Trady AWS Backend  (this repo)
    ↓ HMAC-SHA256
Trading Bot Brain API  (external)
```

### Bot mode

Set `TRADING_BOT_MODE` in `.env`:
- `mock` (default) — deterministic in-memory mock, no external calls
- `real` — proxy to external bot API at `TRADING_BOT_BASE_URL`

### Policy engine

All commands pass through the policy engine regardless of how they arrive (REST or voice). The LLM cannot override policy.

| Tier | Commands |
|------|----------|
| **Auto-allowed** | `bot_status`, `get_metrics`, `get_positions`, `get_logs`, `pause_bot`, `reduce_risk`, `conservative_mode` |
| **Approval required** | `resume_bot`, `emergency_stop`, `flatten_positions`, `increase_risk`, `change_strategy`, `add_symbol`, `disable_stop_loss`, `disable_drawdown_limit` |
| **Always blocked** | `withdraw_funds`, `transfer_funds`, `reveal_api_keys`, `disable_all_safety`, `set_unlimited_leverage` |

---

## API endpoints

### Phase 1 / 2 (unchanged)
```
GET  /health
POST /v1/auth/device
POST /v1/voice/turn
GET  /v1/memory/history
DELETE /v1/memory/history
POST /v1/fcm/test
```

### Phase 3 — Trading Supervisor
```
GET  /v1/trading/health
GET  /v1/trading/status
GET  /v1/trading/metrics
GET  /v1/trading/positions
GET  /v1/trading/logs
POST /v1/trading/command
POST /v1/trading/approve
GET  /v1/trading/audit
POST /v1/trading/events/webhook
```

---

## curl examples

```bash
# Auth
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/device \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"demo-device","deviceName":"Demo Phone"}' | python -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# Bot health
curl http://localhost:8000/v1/trading/health \
  -H "Authorization: Bearer $TOKEN"

# Bot status
curl http://localhost:8000/v1/trading/status \
  -H "Authorization: Bearer $TOKEN"

# Metrics
curl http://localhost:8000/v1/trading/metrics \
  -H "Authorization: Bearer $TOKEN"

# Positions
curl http://localhost:8000/v1/trading/positions \
  -H "Authorization: Bearer $TOKEN"

# Allowed command
curl -X POST http://localhost:8000/v1/trading/command \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"command":"pause_bot","reason":"manual pause","mode":"paper"}'

# Risky command (returns approvalId)
curl -X POST http://localhost:8000/v1/trading/command \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"command":"resume_bot","reason":"resuming after pause","mode":"paper"}'

# Approve
curl -X POST http://localhost:8000/v1/trading/approve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"approvalId":"<uuid>","decision":"approve","userConfirmationText":"I approve resume bot"}'

# Audit log
curl http://localhost:8000/v1/trading/audit \
  -H "Authorization: Bearer $TOKEN"
```

---

## Run tests

```bash
pytest tests/ -v
```

---

## Android emulator URL

Use `http://10.0.2.2:8000` for emulator (routes to PC localhost).
Use `http://<YOUR_PC_IP>:8000` for real device on same Wi-Fi.
Use HTTPS only in production.

---

## Postgres (production)

Set in `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/trady
```
Add `asyncpg` to requirements.txt.

---

## AWS Lightsail deployment notes

See `DEBUGGING_PHASE3.md` for Phase 3 deployment steps.
