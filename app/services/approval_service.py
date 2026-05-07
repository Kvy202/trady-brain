"""
Approval service — persists pending approvals and processes decisions.

Approvals expire after settings.approval_ttl_seconds.
Only the device that created the approval can decide it.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AuditLog, PendingApproval
from app.services import bot_client

logger = logging.getLogger("trady.approval")


def _utcnow() -> datetime:
    """Timezone-aware UTC datetime — safe for both SQLite and PostgreSQL."""
    return datetime.now(timezone.utc)


async def create_approval(
    db: AsyncSession,
    device_id: str,
    command: str,
    reason: str,
    mode: str,
) -> PendingApproval:
    approval_id = str(uuid.uuid4())
    expires_at = _utcnow() + timedelta(seconds=settings.approval_ttl_seconds)
    approval = PendingApproval(
        approval_id=approval_id,
        device_id=device_id,
        command=command,
        reason=reason,
        mode=mode,
        expires_at=expires_at,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    logger.info(f"[Approval] Created {approval_id} for {command!r} device={device_id}")
    return approval


async def decide_approval(
    db: AsyncSession,
    device_id: str,
    approval_id: str,
    decision: str,
    confirmation_text: str | None,
) -> tuple[PendingApproval, int | None]:
    """
    Returns (approval, audit_id).
    Raises ValueError on bad state.
    """
    result = await db.execute(
        select(PendingApproval).where(PendingApproval.approval_id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if approval is None:
        raise ValueError("Approval not found")
    if approval.device_id != device_id:
        raise ValueError("Not your approval")
    if approval.decision is not None:
        raise ValueError(f"Already decided: {approval.decision}")

    # Compare timezone-aware datetimes
    expires = approval.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if _utcnow() > expires:
        raise ValueError("Approval expired")

    decision = decision.strip().lower()
    if decision not in ("approve", "deny"):
        raise ValueError("Decision must be 'approve' or 'deny'")

    approval.decision = decision
    approval.decided_at = _utcnow()
    await db.commit()
    await db.refresh(approval)

    # Execute the command if approved; track whether bot was reachable
    bot_response = None
    bot_executed = False
    if decision == "approve":
        try:
            resp = await bot_client.send_command(
                approval.command, approval.reason or "", approval.mode
            )
            bot_response = str(resp)
            bot_executed = True
            logger.info(f"[Approval] Executed approved command {approval.command!r}")
        except bot_client.BotUnavailableError as exc:
            logger.error(f"[Approval] Bot unavailable after approval: {exc}")
            bot_response = f"bot_unavailable: {exc}"
            bot_executed = False

    # Outcome accurately reflects what happened
    if decision == "deny":
        outcome = "denied"
    elif bot_executed:
        outcome = "approved_executed"
    else:
        outcome = "approved_bot_unavailable"

    audit = AuditLog(
        device_id=device_id,
        command=approval.command,
        reason=f"[decision={decision}] {approval.reason or ''}",
        mode=approval.mode,
        outcome=outcome,
        approval_id=approval_id,
        bot_response=bot_response,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    logger.info(
        f"[Approval] {decision.upper()} approval={approval_id} "
        f"command={approval.command!r} outcome={outcome} audit={audit.id}"
    )
    return approval, audit.id
