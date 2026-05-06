import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def _get_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/v1/auth/device",
        json={"deviceId": "test-trading-device", "deviceName": "Test Phone"},
    )
    assert resp.status_code == 200
    return resp.json()["accessToken"]


@pytest.mark.asyncio
async def test_trading_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.get("/v1/trading/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "demo"
    assert "pnlDay" in data
    assert isinstance(data["positions"], list)


@pytest.mark.asyncio
async def test_trading_pause_no_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/trading/command",
            json={"command": "pause_bot", "reason": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["requiresApproval"] is False


@pytest.mark.asyncio
async def test_trading_resume_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/trading/command",
            json={"command": "resume_bot", "reason": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["requiresApproval"] is True


@pytest.mark.asyncio
async def test_trading_emergency_stop_requires_approval():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        resp = await client.post(
            "/v1/trading/command",
            json={"command": "emergency_stop_demo", "reason": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["requiresApproval"] is True
