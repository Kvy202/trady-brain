# trady-brain

FastAPI backend for the Trady AI Voice Assistant — Phase 2.

## Safety notice

This backend is **demo-only**. It does NOT connect to any real exchange, does NOT place real trades, and does NOT hold real funds. All trading data is in-memory simulation that resets on restart.

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
cp .env.example .env          # edit JWT_SECRET before deploying
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: http://localhost:8000/docs

---

## Quick start (Docker)

```bash
docker compose up --build
```

---

## API — curl examples

### Health
```bash
curl http://localhost:8000/health
```

### Device auth
```bash
curl -X POST http://localhost:8000/v1/auth/device \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"demo-device","deviceName":"Demo Phone"}'
```
Copy `accessToken` from the response.

### Voice turn
```bash
TOKEN="<accessToken>"

curl -X POST http://localhost:8000/v1/voice/turn \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text":"bot status","lang":"en-IN","deviceId":"demo-device"}'
```

### Trading status
```bash
curl http://localhost:8000/v1/trading/status \
  -H "Authorization: Bearer $TOKEN"
```

### Pause demo bot
```bash
curl -X POST http://localhost:8000/v1/trading/command \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"command":"pause_bot","reason":"manual test"}'
```

### Memory history
```bash
curl http://localhost:8000/v1/memory/history \
  -H "Authorization: Bearer $TOKEN"
```

### FCM demo test
```bash
curl -X POST http://localhost:8000/v1/fcm/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"type":"trade_alert","title":"Demo Alert","body":"Drawdown threshold crossed."}'
```

---

## Android emulator URL

Use `http://10.0.2.2:8000` — emulator routes this to your PC localhost.

For a real Android phone on the same Wi-Fi, use `http://<YOUR_PC_IP>:8000`.

For production, use HTTPS only.

---

## Run tests

```bash
pytest tests/ -v
```

---

## Postgres (production)

Set in `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/trady
```
Add `asyncpg` to requirements.txt.
