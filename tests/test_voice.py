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
    assert data["intent"] == "bot_status"
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
    assert resp.json()["requiresApproval"] is True


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
    assert resp.json()["requiresApproval"] is True


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
    assert resp.json()["intent"] == "unknown"


@pytest.mark.asyncio
async def test_voice_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/voice/turn",
            json={"text": "bot status", "lang": "en-IN", "deviceId": "no-token"},
        )
    assert resp.status_code == 403
