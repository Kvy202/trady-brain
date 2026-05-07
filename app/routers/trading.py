"""
Phase 3 trading router.

Endpoints:
  GET  /v1/trading/health
  GET  /v1/trading/status
  GET  /v1/trading/metrics
  GET  /v1/trading/positions
  GET  /v1/trading/logs
  POST /v1/trading/command        ← rate-limited per device
  POST /v1/trading/approve
  GET  /v1/trading/audit
  POST /v1/trading/events/webhook ← HMAC-verified bot events (no device auth)

All command paths run through the policy engine first.
LLM text never bypasses policy.
"""
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_device
from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models import AuditLog, BotEvent, Device
from app.schemas import (
    ApprovalRequest,
    ApprovalResponse,
    AuditEntry,
    AuditLogResponse,
    BotHealthResponse,
    BotLogsResponse,
    BotMetricsResponse,
    BotPositionsResponse,
    BotStatusResponse,
    TradingCommandRequest,
    TradingCommandResponse,
    WebhookEventResponse,
)
from app.services import approval_service, bot_client
from app.services.bot_client import BotUnavailableError
from app.services.policy_engine import PolicyDecision, evaluate

logger = logging.getLogger("trady.trading")
router = APIRouter()


# ── GET /health ───────────────────────────────────────────────────────────────

@router.get("/health", response_model=BotHealthResponse)
async def trading_health(device: Device = Depends(get_current_device)) -> BotHealthResponse:
    logger.info(f"[Trading] Health request from {device.device_id}")
    try:
        data = await bot_client.get_health()
    except BotUnavailableError as exc:
        logger.warning(f"[Trading] Bot unavailable for health: {exc}")
        return BotHealthResponse(online=False, mode="unavailable", version="n/a", uptimeSeconds=0)
    return BotHealthResponse(**data)


# ── GET /status ───────────────────────────────────────────────────────────────

@router.get("/status", response_model=BotStatusResponse)
async def trading_status(device: Device = Depends(get_current_device)) -> BotStatusResponse:
    logger.info(f"[Trading] Status request from {device.device_id}")
    try:
        data = await bot_client.get_status()
    except BotUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Bot unavailable: {exc}")
    return BotStatusResponse(**data)


# ── GET /metrics ──────────────────────────────────────────────────────────────

@router.get("/metrics", response_model=BotMetricsResponse)
async def trading_metrics(device: Device = Depends(get_current_device)) -> BotMetricsResponse:
    logger.info(f"[Trading] Metrics request from {device.device_id}")
    try:
        data = await bot_client.get_metrics()
    except BotUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Bot unavailable: {exc}")
    return BotMetricsResponse(**data)


# ── GET /positions ────────────────────────────────────────────────────────────

@router.get("/positions", response_model=BotPositionsResponse)
async def trading_positions(device: Device = Depends(get_current_device)) -> BotPositionsResponse:
    logger.info(f"[Trading] Positions request from {device.device_id}")
    try:
        data = await bot_client.get_positions()
    except BotUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Bot unavailable: {exc}")
    return BotPositionsResponse(**data)


# ── GET /logs ─────────────────────────────────────────────────────────────────

@router.get("/logs", response_model=BotLogsResponse)
async def trading_logs(device: Device = Depends(get_current_device)) -> BotLogsResponse:
    logger.info(f"[Trading] Logs request from {device.device_id}")
    try:
        data = await bot_client.get_logs()
    except BotUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"Bot unavailable: {exc}")
    return BotLogsResponse(**data)


# ── POST /command  (rate-limited per device) ──────────────────────────────────

@router.post("/command", response_model=TradingCommandResponse)
@limiter.limit(settings.trading_rate_limit)
async def trading_command(
    request: Request,
    body: TradingCommandRequest,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> TradingCommandResponse:
    cmd = body.command.strip().lower()
    mode = (body.mode or "paper").strip().lower()
    reason = body.reason or ""

    logger.info(
        f"[Trading] Command from {device.device_id}: {cmd!r} "
        f"mode={mode!r} reason={reason!r}"
    )

    decision = evaluate(cmd, mode)

    # ── Blocked ───────────────────────────────────────────────────────────────
    if decision == PolicyDecision.BLOCKED:
        await _write_audit(db, device.device_id, cmd, reason, mode, "blocked")
        raise HTTPException(status_code=403, detail=f"Command '{cmd}' is permanently blocked.")

    # ── Unknown ───────────────────────────────────────────────────────────────
    if decision == PolicyDecision.UNKNOWN:
        await _write_audit(db, device.device_id, cmd, reason, mode, "unknown")
        raise HTTPException(status_code=400, detail=f"Unknown command: '{cmd}'")

    # ── Approval required ─────────────────────────────────────────────────────
    if decision == PolicyDecision.APPROVAL_REQUIRED:
        approval = await approval_service.create_approval(
            db, device.device_id, cmd, reason, mode
        )
        audit_id = await _write_audit(
            db, device.device_id, cmd, reason, mode,
            "approval_required", approval_id=approval.approval_id,
        )
        return TradingCommandResponse(
            success=False,
            command=cmd,
            requiresApproval=True,
            approvalId=approval.approval_id,
            message=f"Approval required before executing '{cmd}'.",
            mode=mode,
            riskLevel=_risk_level(cmd),
            auditId=audit_id,
            expiresInSeconds=settings.approval_ttl_seconds,
        )

    # ── Allowed — execute ─────────────────────────────────────────────────────
    try:
        resp = await bot_client.send_command(cmd, reason, mode)
        bot_resp_text = json.dumps(resp)
        audit_id = await _write_audit(
            db, device.device_id, cmd, reason, mode, "allowed",
            bot_response=bot_resp_text,
        )
        return TradingCommandResponse(
            success=True,
            command=cmd,
            requiresApproval=False,
            message=resp.get("message", f"Command '{cmd}' executed."),
            mode=mode,
            riskLevel=_risk_level(cmd),
            auditId=audit_id,
        )
    except BotUnavailableError as exc:
        audit_id = await _write_audit(
            db, device.device_id, cmd, reason, mode, "error",
            bot_response=str(exc),
        )
        raise HTTPException(status_code=503, detail=f"Bot unavailable: {exc}")


# ── POST /approve ─────────────────────────────────────────────────────────────

@router.post("/approve", response_model=ApprovalResponse)
async def trading_approve(
    request: ApprovalRequest,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    logger.info(
        f"[Trading] Approval decision from {device.device_id}: "
        f"id={request.approvalId} decision={request.decision!r}"
    )
    try:
        approval, audit_id = await approval_service.decide_approval(
            db,
            device.device_id,
            request.approvalId,
            request.decision,
            request.userConfirmationText,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ApprovalResponse(
        success=True,
        approvalId=approval.approval_id,
        decision=approval.decision,
        command=approval.command,
        message=f"Decision '{approval.decision}' recorded for '{approval.command}'.",
        auditId=audit_id,
    )


# ── GET /audit ────────────────────────────────────────────────────────────────

@router.get("/audit", response_model=AuditLogResponse)
async def trading_audit(
    limit: int = 50,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    logger.info(f"[Trading] Audit request from {device.device_id}")
    limit = min(limit, 200)
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.device_id == device.device_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return AuditLogResponse(
        items=[
            AuditEntry(
                id=r.id,
                command=r.command,
                outcome=r.outcome,
                mode=r.mode,
                reason=r.reason,
                approvalId=r.approval_id,
                timestamp=r.timestamp.isoformat(),
            )
            for r in rows
        ]
    )


# ── POST /events/webhook ──────────────────────────────────────────────────────
# No device auth — this endpoint is called by the bot server, not the Android app.
# Security is provided by HMAC signature verification.

@router.post("/events/webhook", response_model=WebhookEventResponse)
async def bot_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_trady_timestamp: Optional[str] = Header(None),
    x_trady_signature: Optional[str] = Header(None),
) -> WebhookEventResponse:
    body = await request.body()
    source_ip = request.client.host if request.client else "unknown"

    # ── Reject missing headers ────────────────────────────────────────────────
    if not x_trady_timestamp or not x_trady_signature:
        logger.warning(f"[Webhook] Missing HMAC headers from {source_ip}")
        raise HTTPException(status_code=400, detail="Missing webhook signature headers")

    # ── Reject stale timestamps ───────────────────────────────────────────────
    try:
        ts = int(x_trady_timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    age = abs(int(time.time()) - ts)
    if age > settings.webhook_max_age_seconds:
        logger.warning(f"[Webhook] Stale event from {source_ip} age={age}s")
        raise HTTPException(status_code=400, detail="Webhook event is stale")

    # ── Verify HMAC ───────────────────────────────────────────────────────────
    expected = hmac.new(
        settings.trading_bot_webhook_secret.encode(),
        x_trady_timestamp.encode() + b"\n" + body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, x_trady_signature):
        logger.warning(f"[Webhook] Invalid HMAC from {source_ip}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # ── Parse and store ───────────────────────────────────────────────────────
    try:
        payload_obj = json.loads(body)
        event_type = payload_obj.get("type", "unknown")
    except json.JSONDecodeError:
        event_type = "raw"

    event = BotEvent(
        event_type=event_type,
        payload=body.decode("utf-8", errors="replace"),
        source_ip=source_ip,
        verified=True,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    logger.info(f"[Webhook] Accepted event id={event.id} type={event_type!r} from {source_ip}")
    return WebhookEventResponse(accepted=True, eventId=event.id)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _write_audit(
    db: AsyncSession,
    device_id: str,
    command: str,
    reason: str,
    mode: str,
    outcome: str,
    approval_id: str | None = None,
    bot_response: str | None = None,
) -> int:
    audit = AuditLog(
        device_id=device_id,
        command=command,
        reason=reason,
        mode=mode,
        outcome=outcome,
        approval_id=approval_id,
        bot_response=bot_response,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit.id


def _risk_level(command: str) -> str:
    low = {"bot_status", "get_metrics", "get_positions", "get_logs"}
    high = {"emergency_stop", "flatten_positions", "increase_risk", "disable_stop_loss"}
    if command in low:
        return "low"
    if command in high:
        return "high"
    return "medium"
