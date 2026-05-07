from typing import Any, Dict, List, Optional

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
    data: Dict[str, Any] = Field(default_factory=dict)


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


# ── Trading positions ─────────────────────────────────────────────────────────

class TradingPosition(BaseModel):
    symbol: str
    side: str
    size: str
    pnl: float


# ── Trading status (used by trading_supervisor for voice replies) ─────────────

class TradingStatusResponse(BaseModel):
    online: bool
    mode: str
    pnlDay: float
    riskMode: str
    drawdown: float
    positions: List[TradingPosition]


# ── Bot health / status / metrics ─────────────────────────────────────────────

class BotHealthResponse(BaseModel):
    online: bool
    mode: str          # mock | paper | live | unavailable
    version: str
    uptimeSeconds: int


class BotStatusResponse(BaseModel):
    online: bool
    mode: str
    pnlDay: float
    riskMode: str
    drawdown: float
    positions: List[TradingPosition]
    activeSymbols: List[str]
    lastHeartbeat: str


class BotMetricsResponse(BaseModel):
    pnlDay: float
    pnlWeek: float
    pnlMonth: float
    drawdown: float
    sharpe: float
    winRate: float
    totalTrades: int
    mode: str


class BotPositionsResponse(BaseModel):
    positions: List[TradingPosition]
    mode: str
    totalExposure: float


class BotLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str


class BotLogsResponse(BaseModel):
    logs: List[BotLogEntry]
    mode: str


# ── Trading commands ──────────────────────────────────────────────────────────

class TradingCommandRequest(BaseModel):
    command: str
    reason: Optional[str] = None
    mode: Optional[str] = "paper"   # paper | live (live always triggers approval check)


class TradingCommandResponse(BaseModel):
    success: bool
    command: str
    requiresApproval: bool
    approvalId: Optional[str] = None
    message: str
    mode: str = "mock"
    riskLevel: str = "medium"
    auditId: Optional[int] = None
    expiresInSeconds: Optional[int] = None


# ── Approval ──────────────────────────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    approvalId: str
    decision: str                         # "approve" | "deny"
    userConfirmationText: Optional[str] = None


class ApprovalResponse(BaseModel):
    success: bool
    approvalId: str
    decision: str
    command: str
    message: str
    auditId: Optional[int] = None


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    id: int
    command: str
    outcome: str
    mode: str
    reason: Optional[str]
    approvalId: Optional[str]
    timestamp: str


class AuditLogResponse(BaseModel):
    items: List[AuditEntry]


# ── Webhook ───────────────────────────────────────────────────────────────────

class WebhookEventResponse(BaseModel):
    accepted: bool
    eventId: int


# ── FCM ───────────────────────────────────────────────────────────────────────

class FcmTestRequest(BaseModel):
    deviceToken: Optional[str] = None
    type: str = "trade_alert"
    title: str = "Demo Trade Alert"
    body: str = "Drawdown crossed demo threshold."


class FcmTestResponse(BaseModel):
    success: bool
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
