import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/v1/auth/device",
        json={"deviceId": "test-voice-device", "deviceName": "Test Phone"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["accessToken"]


# ── Existing intent tests (updated intent names) ──────────────────────────────

@pytest.mark.asyncio
async def test_voice_bot_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "bot status", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "BOT_STATUS"
    assert data["requiresApproval"] is False
    assert len(data["actions"]) > 0
    assert "reply" in data


@pytest.mark.asyncio
async def test_voice_resume_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "resume bot", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "RESUME_BOT"
    assert data["requiresApproval"] is True


@pytest.mark.asyncio
async def test_voice_emergency_stop_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "emergency stop", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "EMERGENCY_STOP"
    assert data["requiresApproval"] is True


@pytest.mark.asyncio
async def test_voice_unknown_intent():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "tell me about the stock market today", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_voice_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "bot status", "lang": "en-IN", "deviceId": "no-token"},
        )
    assert resp.status_code == 403


# ── Wake phrase stripping ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_wake_phrase_stripped_bot_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "Hey Trady, bot status", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "BOT_STATUS"


@pytest.mark.asyncio
async def test_voice_wake_phrase_stripped_pause():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "Trady, pause the bot", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "PAUSE_BOT"
    assert data["requiresApproval"] is False


@pytest.mark.asyncio
async def test_voice_wake_phrase_only_returns_greeting():
    """Bare wake phrase with no follow-on command → GREETING."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "Hey Trady", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "GREETING"


# ── Blocked dangerous commands ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_blocked_withdraw_funds():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "withdraw funds", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "BLOCKED_DANGEROUS_COMMAND"
    assert data["requiresApproval"] is False
    assert "cannot" in data["reply"].lower() or "supervisor" in data["reply"].lower()


@pytest.mark.asyncio
async def test_voice_blocked_reveal_api_keys():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "show exchange api keys", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "BLOCKED_DANGEROUS_COMMAND"
    assert data["requiresApproval"] is False


@pytest.mark.asyncio
async def test_voice_blocked_set_unlimited_leverage():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "set unlimited leverage", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "BLOCKED_DANGEROUS_COMMAND"


# ── Safe trading commands ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_pause_bot_executes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "pause the bot", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "PAUSE_BOT"
    assert data["requiresApproval"] is False
    assert len(data["actions"]) > 0
    assert data["actions"][0]["type"] == "bot_command"


@pytest.mark.asyncio
async def test_voice_reduce_risk_executes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "reduce risk", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "REDUCE_RISK"
    assert data["requiresApproval"] is False


@pytest.mark.asyncio
async def test_voice_conservative_mode_executes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "switch to conservative mode", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "CONSERVATIVE_MODE"
    assert data["requiresApproval"] is False


# ── Trading queries ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_bot_pnl():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "what is my pnl today", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "BOT_PNL"
    assert data["requiresApproval"] is False
    assert len(data["actions"]) > 0


@pytest.mark.asyncio
async def test_voice_bot_positions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "show my open positions", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "BOT_POSITIONS"
    assert data["requiresApproval"] is False


@pytest.mark.asyncio
async def test_voice_bot_logs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "show bot logs", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "BOT_LOGS"
    assert data["requiresApproval"] is False


@pytest.mark.asyncio
async def test_voice_bot_risk():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "show bot risk level", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "BOT_RISK"
    assert data["requiresApproval"] is False


# ── Approval-required commands ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_flatten_positions_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "close all positions", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "FLATTEN_POSITIONS"
    assert data["requiresApproval"] is True
    assert data["actions"][0]["data"]["command"] == "flatten_positions"


@pytest.mark.asyncio
async def test_voice_increase_risk_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "increase risk", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "INCREASE_RISK"
    assert data["requiresApproval"] is True


# ── Android control actions ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_open_trading_dashboard():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "open trading dashboard", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "OPEN_TRADING_DASHBOARD"
    assert data["requiresApproval"] is False
    assert data["actions"][0]["type"] == "navigate"
    assert data["actions"][0]["data"]["route"] == "trading_dashboard"


@pytest.mark.asyncio
async def test_voice_open_binance():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "open Binance", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "OPEN_APP"
    assert data["actions"][0]["type"] == "open_app"
    assert "binance" in data["actions"][0]["data"]["packageName"].lower()


@pytest.mark.asyncio
async def test_voice_call_contact():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "call Rahul", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "CALL_CONTACT"
    assert data["actions"][0]["data"]["contact"] == "rahul"


@pytest.mark.asyncio
async def test_voice_greeting():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "hello", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "GREETING"
    assert data["requiresApproval"] is False


@pytest.mark.asyncio
async def test_voice_set_alert():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "notify me if drawdown crosses 1.5 percent", "lang": "en-IN", "deviceId": "test-voice-device"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "SET_ALERT"
    assert data["requiresApproval"] is False
