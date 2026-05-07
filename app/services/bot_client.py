"""
Bot client — abstracts mock vs real trading bot API.

Mock mode: returns deterministic in-memory state (safe for dev/test).
Real mode: signs requests with HMAC-SHA256 and calls external bot API.

Neither mode places real trades. Real mode is a supervisor channel only.
"""
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

from app.config import settings

logger = logging.getLogger("trady.bot_client")

# ── Mock in-memory state ──────────────────────────────────────────────────────

_mock_state: Dict[str, Any] = {
    "online": True,
    "mode": "mock",
    "version": "mock-1.0.0",
    "uptimeSeconds": 3600,
    "pnlDay": 0.7,
    "pnlWeek": 2.1,
    "pnlMonth": 5.4,
    "riskMode": "medium",
    "drawdown": 0.3,
    "sharpe": 1.42,
    "winRate": 0.61,
    "totalTrades": 47,
    "totalExposure": 1200.0,
    "lastHeartbeat": "2024-01-01T00:00:00Z",
    "activeSymbols": ["BTCUSDT", "ETHUSDT"],
    "positions": [
        {"symbol": "BTCUSDT", "side": "long", "size": "demo-small", "pnl": 0.4},
        {"symbol": "ETHUSDT", "side": "long", "size": "demo-micro", "pnl": 0.3},
    ],
    "logs": [
        {"timestamp": "2024-01-01T00:00:01Z", "level": "INFO",  "message": "Mock bot started"},
        {"timestamp": "2024-01-01T00:00:02Z", "level": "INFO",  "message": "Connected to mock exchange"},
        {"timestamp": "2024-01-01T00:00:03Z", "level": "DEBUG", "message": "Heartbeat OK"},
    ],
}

_MOCK_COMMAND_RESULTS: Dict[str, Dict[str, Any]] = {
    "bot_status":        {"ok": True, "message": "Mock bot status retrieved."},
    "get_metrics":       {"ok": True, "message": "Mock metrics returned."},
    "get_positions":     {"ok": True, "message": "Mock positions returned."},
    "get_logs":          {"ok": True, "message": "Mock logs returned."},
    "pause_bot":         {"ok": True, "message": "Mock bot paused safely."},
    "reduce_risk":       {"ok": True, "message": "Mock risk reduced to low."},
    "conservative_mode": {"ok": True, "message": "Mock bot switched to conservative mode."},
}


def _apply_mock_command(command: str) -> None:
    if command == "pause_bot":
        _mock_state["online"] = False
    elif command == "resume_bot":
        _mock_state["online"] = True
    elif command == "reduce_risk":
        _mock_state["riskMode"] = "low"
    elif command == "conservative_mode":
        _mock_state["riskMode"] = "conservative"
    elif command == "emergency_stop":
        _mock_state["online"] = False
        _mock_state["positions"] = []
    elif command == "flatten_positions":
        _mock_state["positions"] = []


# ── HMAC signing ──────────────────────────────────────────────────────────────

def _build_hmac_headers(method: str, path: str, body: bytes) -> Dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    payload = f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n".encode() + body
    signature = hmac.new(
        settings.trading_bot_hmac_secret.encode(),
        payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return {
        "X-Trady-Timestamp": timestamp,
        "X-Trady-Nonce": nonce,
        "X-Trady-Signature": signature,
        "X-Trady-Api-Key": settings.trading_bot_api_key,
        "Content-Type": "application/json",
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def get_health() -> Dict[str, Any]:
    if settings.trading_bot_mode == "mock":
        return {
            "online": _mock_state["online"],
            "mode": _mock_state["mode"],
            "version": _mock_state["version"],
            "uptimeSeconds": _mock_state["uptimeSeconds"],
        }
    return await _real_get("/bot/v1/health")


async def get_status() -> Dict[str, Any]:
    if settings.trading_bot_mode == "mock":
        return {
            "online": _mock_state["online"],
            "mode": _mock_state["mode"],
            "pnlDay": _mock_state["pnlDay"],
            "riskMode": _mock_state["riskMode"],
            "drawdown": _mock_state["drawdown"],
            "positions": _mock_state["positions"],
            "activeSymbols": _mock_state["activeSymbols"],
            "lastHeartbeat": datetime.now(timezone.utc).isoformat(),
        }
    return await _real_get("/bot/v1/status")


async def get_metrics() -> Dict[str, Any]:
    if settings.trading_bot_mode == "mock":
        return {
            "pnlDay":      _mock_state["pnlDay"],
            "pnlWeek":     _mock_state["pnlWeek"],
            "pnlMonth":    _mock_state["pnlMonth"],
            "drawdown":    _mock_state["drawdown"],
            "sharpe":      _mock_state["sharpe"],
            "winRate":     _mock_state["winRate"],
            "totalTrades": _mock_state["totalTrades"],
            "mode":        _mock_state["mode"],
        }
    return await _real_get("/bot/v1/metrics")


async def get_positions() -> Dict[str, Any]:
    if settings.trading_bot_mode == "mock":
        return {
            "positions":     _mock_state["positions"],
            "mode":          _mock_state["mode"],
            "totalExposure": _mock_state["totalExposure"],
        }
    return await _real_get("/bot/v1/positions")


async def get_logs() -> Dict[str, Any]:
    if settings.trading_bot_mode == "mock":
        return {"logs": _mock_state["logs"], "mode": _mock_state["mode"]}
    return await _real_get("/bot/v1/logs")


async def send_command(command: str, reason: str, mode: str) -> Dict[str, Any]:
    if settings.trading_bot_mode == "mock":
        result = _MOCK_COMMAND_RESULTS.get(
            command, {"ok": True, "message": f"Mock: command {command!r} acknowledged."}
        )
        _apply_mock_command(command)
        return result
    body = json.dumps({"command": command, "reason": reason, "mode": mode}).encode()
    return await _real_post("/bot/v1/command", body)


# ── Real bot HTTP helpers (fail-closed) ───────────────────────────────────────

async def _real_get(path: str) -> Dict[str, Any]:
    url = settings.trading_bot_base_url.rstrip("/") + path
    headers = _build_hmac_headers("GET", path, b"")
    try:
        async with httpx.AsyncClient(timeout=settings.trading_bot_timeout_seconds) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        logger.error(f"[BotClient] Timeout on GET {path}")
        raise BotUnavailableError("Bot API timed out")
    except httpx.HTTPStatusError as exc:
        logger.error(f"[BotClient] HTTP {exc.response.status_code} on GET {path}")
        raise BotUnavailableError(f"Bot API error {exc.response.status_code}")
    except Exception as exc:
        logger.error(f"[BotClient] Unexpected error on GET {path}: {type(exc).__name__}")
        raise BotUnavailableError("Bot API unreachable")


async def _real_post(path: str, body: bytes) -> Dict[str, Any]:
    url = settings.trading_bot_base_url.rstrip("/") + path
    headers = _build_hmac_headers("POST", path, body)
    try:
        async with httpx.AsyncClient(timeout=settings.trading_bot_timeout_seconds) as client:
            resp = await client.post(url, content=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        logger.error(f"[BotClient] Timeout on POST {path}")
        raise BotUnavailableError("Bot API timed out")
    except httpx.HTTPStatusError as exc:
        logger.error(f"[BotClient] HTTP {exc.response.status_code} on POST {path}")
        raise BotUnavailableError(f"Bot API error {exc.response.status_code}")
    except Exception as exc:
        logger.error(f"[BotClient] Unexpected error on POST {path}: {type(exc).__name__}")
        raise BotUnavailableError("Bot API unreachable")


class BotUnavailableError(Exception):
    """Raised when the bot API cannot be reached. Callers must fail closed."""
