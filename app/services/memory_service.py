import logging
from typing import List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationTurn
from app.schemas import MemoryItem

logger = logging.getLogger("trady.memory_service")


async def save_turn(db: AsyncSession, device_id: str, role: str, message: str, intent: str | None = None) -> None:
    turn = ConversationTurn(device_id=device_id, role=role, message=message, intent=intent)
    db.add(turn)
    await db.commit()
    logger.debug(f"[MemoryService] Saved {role} turn for {device_id}: '{message[:60]}'")


async def get_history(db: AsyncSession, device_id: str) -> List[MemoryItem]:
    result = await db.execute(
        select(ConversationTurn)
        .where(ConversationTurn.device_id == device_id)
        .order_by(ConversationTurn.id.asc())
    )
    turns = result.scalars().all()
    return [
        MemoryItem(
            id=t.id,
            role=t.role,
            message=t.message,
            timestamp=t.timestamp.isoformat() if t.timestamp else "",
        )
        for t in turns
    ]


async def clear_history(db: AsyncSession, device_id: str) -> None:
    await db.execute(delete(ConversationTurn).where(ConversationTurn.device_id == device_id))
    await db.commit()
    logger.info(f"[MemoryService] History cleared for {device_id}")
