from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ── Auth ─────────────────────────────────────────────────────────────────────

class DeviceAuthRequest(BaseModel):
    deviceId: str
    deviceName: str


class DeviceAuthResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"
    expiresIn: int = 3600


# ── Voice ─────────────────────────────────────────────────────────────────────

class VoiceTurnRequest(BaseModel):
    text: str
    lang: str = "en-IN"
    deviceId: str


class VoiceAction(BaseModel):
    type: str
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class VoiceTurnResponse(BaseModel):
    reply: str
    status: str = "success"
    intent: str
    requiresApproval: bool = False
    actions: List[VoiceAction] = Field(default_factory=list)


# ── Memory ────────────────────────────────────────────────────────────────────

class MemoryItem(BaseModel):
    id: int
    role: str
    message: str
    timestamp: str


class MemoryHistoryResponse(BaseModel):
    items: List[MemoryItem]


class ClearHistoryResponse(BaseModel):
    success: bool


# ── Trading (demo only — no real trading) ────────────────────────────────────

class TradingPosition(BaseModel):
    symbol: str
    side: str
    size: str
    pnl: float


class TradingStatusResponse(BaseModel):
    online: bool
    mode: str
    pnlDay: float
    riskMode: str
    drawdown: float
    positions: List[TradingPosition]


class TradingCommandRequest(BaseModel):
    command: str
    reason: Optional[str] = None


class TradingCommandResponse(BaseModel):
    success: bool
    command: str
    requiresApproval: bool
    message: str


# ── FCM ───────────────────────────────────────────────────────────────────────

class FcmTestRequest(BaseModel):
    deviceToken: Optional[str] = None
    type: str = "trade_alert"
    title: str = "Demo Trade Alert"
    body: str = "Drawdown crossed demo threshold."


class FcmTestResponse(BaseModel):
    success: bool
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
