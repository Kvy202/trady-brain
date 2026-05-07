# Trady Security Model — Phase 3

## Architecture boundary

```
Android App  →  Trady Backend  →  Bot Brain API
   (JWT)        (HMAC SHA256)     (supervisor only)
```

Trady is a **supervisor layer**, not a trading engine. It never holds exchange credentials.

---

## What Trady never does

- Never stores exchange API keys
- Never places real orders
- Never calls exchange WebSocket or REST directly
- Never allows LLM text to bypass the policy engine
- Never logs JWT tokens, API keys, or HMAC secrets
- Never executes blocked commands under any circumstance

---

## Authentication

### Device → Backend (JWT)
- HS256 signed access tokens, 60-minute TTL
- 30-day refresh tokens stored hashed in DB
- All trading endpoints require valid JWT
- Set `JWT_SECRET` to a cryptographically random 256-bit value in production

### Backend → Bot API (HMAC SHA256)
- Every outbound request carries:
  - `X-Trady-Timestamp` — Unix epoch seconds
  - `X-Trady-Nonce` — random UUID hex
  - `X-Trady-Signature` — HMAC-SHA256 over `METHOD\nPATH\nTIMESTAMP\nNONCE\n<body>`
- Set `TRADING_BOT_HMAC_SECRET` to a cryptographically random 256-bit value
- Nonce prevents replay within the same second

### Bot → Backend webhook (HMAC SHA256)
- Incoming events must include `X-Trady-Timestamp` and `X-Trady-Signature`
- Timestamps older than `WEBHOOK_MAX_AGE_SECONDS` (default 60s) are rejected
- Signature covers `TIMESTAMP\n<body>`
- Set `TRADING_BOT_WEBHOOK_SECRET` independently from the outbound secret

---

## Policy engine

Order of evaluation (cannot be overridden by LLM or request payload):

1. **Blocked** → HTTP 403, logged, no state change, ever
2. **Approval required** → HTTP 200 with `requiresApproval=true` and `approvalId`, no execution
3. **Allowed** → execute, log
4. **Unknown** → HTTP 400, logged

Risk-increasing commands (`increase_risk`, `disable_stop_loss`, `disable_drawdown_limit`) are **always** in the approval-required tier.

Live mode (`mode=live`) promotes any non-explicitly-allowed command to approval-required.

---

## Approval workflow

1. User sends risky command → backend returns `approvalId` (UUID, 300s TTL)
2. App shows approval card with command, reason, expiry
3. User explicitly taps Approve/Deny
4. Backend records decision, executes (if approved) or discards
5. Approvals are single-use — double-submission returns 400
6. Only the device that created the approval can decide it

---

## Audit log

Every command attempt is written to `audit_logs` before any response:
- `device_id`, `command`, `reason`, `mode`, `outcome`, `approval_id`, `timestamp`
- Bot response snapshot stored (no secrets)
- Logs are immutable — no DELETE endpoint
- Audit is scoped per-device; no cross-device access

---

## Fail-closed behavior

If the bot API is unreachable or returns an error:
- Allowed commands: HTTP 503, nothing executed
- The system never pretends success on failure
- Mock mode is always available as a safe fallback

---

## Production checklist

- [ ] `JWT_SECRET` — random 256-bit, stored in AWS Secrets Manager
- [ ] `TRADING_BOT_HMAC_SECRET` — random 256-bit, different from JWT secret
- [ ] `TRADING_BOT_WEBHOOK_SECRET` — random 256-bit, different from HMAC secret
- [ ] `TRADING_BOT_API_KEY` — rotate regularly
- [ ] `DATABASE_URL` — PostgreSQL, not SQLite
- [ ] HTTPS only — no HTTP in production
- [ ] CORS `allow_origins` — restrict to your domain
- [ ] `TRADING_BOT_MODE=real` only after bot API is audited and tested
- [ ] Review `TRADING_BOT_ALLOWED_COMMANDS` before production
- [ ] Ensure bot API validates Trady's HMAC on its side
- [ ] Rotate all secrets if any are suspected compromised

---

## What is NOT in scope for Trady

Trady does not protect against:
- Compromise of the trading bot brain itself
- Exchange account security (2FA, IP allowlisting on the exchange)
- Physical device compromise (Android hardware)

These are the responsibility of the trading bot operator and the user.
