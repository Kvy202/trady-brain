"""
Phase 3 trading tests.

Covers:
- mock health / status / metrics / positions / logs
- allowed command (no approval needed)
- approval-required command
- blocked command
- unknown command
- audit log created
- webhook valid signature accepted
- webhook invalid signature rejected
- webhook stale timestamp rejected
- bot client timeout → fail-closed 503
- no secrets in audit log response
"""
import hashlib
import hmac
import json
import time

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.config import settings


# ── Auth helper ───────────────────────────────────────────────────────────────

async def _token(client: AsyncClient, device_id: str = "test-p3-device") -> str:
    resp = await client.post(
        "/v1/auth/device",
        json={"deviceId": device_id, "deviceName": "P3 Test Phone"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["accessToken"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── GET endpoints ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trading_health_mock():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c)
        r = await c.get("/v1/trading/health", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["online"], bool)   # state may vary across test order
    assert data["mode"] == "mock"
    assert "version" in data
    assert "uptimeSeconds" in data


@pytest.mark.asyncio
async def test_trading_status_mock():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c)
        r = await c.get("/v1/trading/status", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "pnlDay" in data
    assert "positions" in data
    assert isinstance(data["positions"], list)
    assert data["mode"] == "mock"


@pytest.mark.asyncio
async def test_trading_metrics_mock():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c)
        r = await c.get("/v1/trading/metrics", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "pnlDay" in data
    assert "sharpe" in data
    assert "winRate" in data


@pytest.mark.asyncio
async def test_trading_positions_mock():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c)
        r = await c.get("/v1/trading/positions", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "positions" in data
    assert isinstance(data["positions"], list)


@pytest.mark.asyncio
async def test_trading_logs_mock():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c)
        r = await c.get("/v1/trading/logs", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)


# ── Command: allowed ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_command_pause_bot_allowed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-pause-device")
        r = await c.post(
            "/v1/trading/command",
            json={"command": "pause_bot", "reason": "unit test", "mode": "paper"},
            headers=_auth(token),
        )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["requiresApproval"] is False
    assert data["auditId"] is not None


@pytest.mark.asyncio
async def test_command_reduce_risk_allowed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-reduce-device")
        r = await c.post(
            "/v1/trading/command",
            json={"command": "reduce_risk", "reason": "unit test", "mode": "paper"},
            headers=_auth(token),
        )
    assert r.status_code == 200
    assert r.json()["success"] is True


# ── Command: approval required ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_command_resume_bot_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-resume-device")
        r = await c.post(
            "/v1/trading/command",
            json={"command": "resume_bot", "reason": "test", "mode": "paper"},
            headers=_auth(token),
        )
    assert r.status_code == 200
    data = r.json()
    assert data["requiresApproval"] is True
    assert data["approvalId"] is not None
    assert data["expiresInSeconds"] == settings.approval_ttl_seconds
    assert data["success"] is False


@pytest.mark.asyncio
async def test_command_emergency_stop_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-estop-device")
        r = await c.post(
            "/v1/trading/command",
            json={"command": "emergency_stop", "reason": "test", "mode": "paper"},
            headers=_auth(token),
        )
    assert r.status_code == 200
    assert r.json()["requiresApproval"] is True


# ── Command: blocked ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_command_blocked():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-blocked-device")
        r = await c.post(
            "/v1/trading/command",
            json={"command": "withdraw_funds", "reason": "test", "mode": "paper"},
            headers=_auth(token),
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_command_reveal_keys_blocked():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-reveal-device")
        r = await c.post(
            "/v1/trading/command",
            json={"command": "reveal_api_keys", "reason": "test"},
            headers=_auth(token),
        )
    assert r.status_code == 403


# ── Command: unknown ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_command_unknown_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-unk-device")
        r = await c.post(
            "/v1/trading/command",
            json={"command": "hack_exchange", "reason": "test"},
            headers=_auth(token),
        )
    assert r.status_code == 400


# ── Approval flow ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approval_flow_approve():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-approve-device")
        # Step 1: issue risky command → get approvalId
        r1 = await c.post(
            "/v1/trading/command",
            json={"command": "resume_bot", "reason": "approval flow test", "mode": "paper"},
            headers=_auth(token),
        )
        assert r1.status_code == 200
        approval_id = r1.json()["approvalId"]
        assert approval_id is not None

        # Step 2: approve
        r2 = await c.post(
            "/v1/trading/approve",
            json={
                "approvalId": approval_id,
                "decision": "approve",
                "userConfirmationText": "I approve resume bot",
            },
            headers=_auth(token),
        )
    assert r2.status_code == 200
    data = r2.json()
    assert data["success"] is True
    assert data["decision"] == "approve"
    assert data["command"] == "resume_bot"


@pytest.mark.asyncio
async def test_approval_flow_deny():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-deny-device")
        r1 = await c.post(
            "/v1/trading/command",
            json={"command": "flatten_positions", "reason": "deny test", "mode": "paper"},
            headers=_auth(token),
        )
        approval_id = r1.json()["approvalId"]
        r2 = await c.post(
            "/v1/trading/approve",
            json={"approvalId": approval_id, "decision": "deny"},
            headers=_auth(token),
        )
    assert r2.status_code == 200
    assert r2.json()["decision"] == "deny"


# ── Audit log ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_log_created():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-audit-device")
        await c.post(
            "/v1/trading/command",
            json={"command": "pause_bot", "reason": "audit test"},
            headers=_auth(token),
        )
        r = await c.get("/v1/trading/audit", headers=_auth(token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["command"] == "pause_bot"


@pytest.mark.asyncio
async def test_audit_log_no_secrets():
    """Audit log items must not contain JWT tokens or API keys."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-nosecret-device")
        await c.post(
            "/v1/trading/command",
            json={"command": "pause_bot", "reason": "secret check"},
            headers=_auth(token),
        )
        r = await c.get("/v1/trading/audit", headers=_auth(token))
    raw = r.text
    assert "trady-dev-secret" not in raw
    assert "CHANGE-IN-PRODUCTION" not in raw


# ── Webhook ───────────────────────────────────────────────────────────────────

def _make_webhook_headers(body: bytes, secret: str, ts: int | None = None) -> dict:
    ts = ts or int(time.time())
    sig = hmac.new(
        secret.encode(),
        str(ts).encode() + b"\n" + body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return {
        "X-Trady-Timestamp": str(ts),
        "X-Trady-Signature": sig,
        "Content-Type": "application/json",
    }


@pytest.mark.asyncio
async def test_webhook_valid_signature():
    body = json.dumps({"type": "bot_alert", "message": "drawdown crossed"}).encode()
    headers = _make_webhook_headers(body, settings.trading_bot_webhook_secret)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/trading/events/webhook", content=body, headers=headers)
    assert r.status_code == 200
    assert r.json()["accepted"] is True


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected():
    body = json.dumps({"type": "bot_alert"}).encode()
    headers = _make_webhook_headers(body, "wrong-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/trading/events/webhook", content=body, headers=headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_stale_timestamp_rejected():
    body = json.dumps({"type": "bot_alert"}).encode()
    stale_ts = int(time.time()) - 120   # 2 minutes ago
    headers = _make_webhook_headers(body, settings.trading_bot_webhook_secret, ts=stale_ts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/trading/events/webhook", content=body, headers=headers)
    assert r.status_code == 400
    assert "stale" in r.json()["detail"].lower()


# ── Fail-closed on bot API unavailable ───────────────────────────────────────

@pytest.mark.asyncio
async def test_bot_unavailable_fail_closed():
    from app.services.bot_client import BotUnavailableError
    with patch(
        "app.routers.trading.bot_client.send_command",
        new_callable=AsyncMock,
        side_effect=BotUnavailableError("timed out"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            token = await _token(c, "test-failclosed-device")
            r = await c.post(
                "/v1/trading/command",
                json={"command": "pause_bot", "reason": "timeout test"},
                headers=_auth(token),
            )
    assert r.status_code == 503


# ── Rate limiting ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_command_endpoint():
    """POST /v1/trading/command is rate-limited; hammering it returns 429."""
    from app.config import settings as cfg
    # Parse the limit number from e.g. "20/minute"
    limit_n = int(cfg.trading_rate_limit.split("/")[0])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        token = await _token(c, "test-ratelimit-device")
        status_codes = []
        for _ in range(limit_n + 5):
            r = await c.post(
                "/v1/trading/command",
                json={"command": "pause_bot", "reason": "rate limit test"},
                headers=_auth(token),
            )
            status_codes.append(r.status_code)

    assert 429 in status_codes, f"Expected 429 after {limit_n} requests, got: {set(status_codes)}"


# ── Unauthenticated requests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trading_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/v1/trading/status")
    assert r.status_code == 403
