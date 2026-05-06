# Trady Phase 2 — Debugging Guide

---

## Backend debug checklist

### Server won't start

```
ModuleNotFoundError: No module named 'app'
```
Run from the `trady-brain/` folder, not from inside `app/`.

```
pydantic_settings not found
```
`pip install pydantic-settings`

---

### 401 on every request

1. Missing `Authorization: Bearer <token>` header.
2. Token expired (default 60 min) — call `/v1/auth/device` again to re-issue.
3. JWT_SECRET in `.env` doesn't match the one used when token was issued.
   Fix: delete `trady.db`, restart server, re-authenticate.

---

### Database errors (SQLite)

```
OperationalError: unable to open database file
```
The `trady.db` file is created automatically next to `main.py`.
Ensure the working directory is `trady-brain/`.

---

### Tests failing

```
RuntimeError: Task attached to a different loop
```
Add `pytest.ini` or `pyproject.toml`:
```ini
[pytest]
asyncio_mode = auto
```

---

## Android debug checklist

All logs are tagged `TradyDebug`. Filter in Logcat:

```
tag:TradyDebug
```

---

### App shows "Local Demo" even after saving URL

1. URL is blank — make sure to press **Save URL** in Settings.
2. URL must not have a trailing slash — backend normalises, but double-check.
3. Restart app after saving URL.

---

### "Backend Error" status after saving URL

1. Confirm backend is running: `curl http://<url>/health`
2. Emulator: use `http://10.0.2.2:8000` — NOT `http://localhost:8000`.
3. Real device: use `http://<PC_LAN_IP>:8000` — NOT `localhost`.
4. HTTP on Android: only allowed in debug builds via `network_security_config.xml`.
   Release builds require HTTPS.
5. Check Logcat for the exact error:
   - `ConnectException` → backend not running or wrong IP/port
   - `SSLException` → using HTTPS for HTTP server or wrong cert
   - `HttpException 401` → auth failed, check token

---

### Auth keeps failing

1. Press **Test Auth** in Developer Settings.
2. Check Logcat for `[BackendRepository] Auth failed`.
3. Confirm `/v1/auth/device` returns 200 via curl.
4. Clear token: Settings → **Clear Token** (or reinstall app).

---

### Voice works in fake mode but not in backend mode

1. Check that `BACKEND_QUERY` intent is being routed:
   Logcat → `CommandRouter.route text=...`
2. Check that BackendRepository is using real API:
   Logcat → `[BackendRepository] voiceTurn`
3. If you see `using fake backend`, the URL is still blank.

---

### FCM test does nothing

Phase 2 FCM is demo-only. The payload is logged on the backend but nothing is sent.
To enable real FCM:
1. Add `google-services.json` to `app/`
2. Uncomment Firebase deps in `app/build.gradle.kts`
3. Uncomment the google-services plugin in both `build.gradle.kts` files
4. Extend `TradyFirebaseMessagingService` and uncomment `onNewToken` / `onMessageReceived`
5. Set `FCM_ENABLED=true` in `.env` and wire Firebase Admin SDK on the backend

---

## Useful curl one-liners

```bash
# Full flow test
BASE=http://localhost:8000

# 1. Health
curl $BASE/health

# 2. Auth
TOKEN=$(curl -s -X POST $BASE/v1/auth/device \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"debug-device","deviceName":"Debug"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo "Token: ${TOKEN:0:20}..."

# 3. Voice turn
curl -s -X POST $BASE/v1/voice/turn \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text":"bot status","lang":"en-IN","deviceId":"debug-device"}' | python3 -m json.tool

# 4. Trading status
curl -s $BASE/v1/trading/status -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
