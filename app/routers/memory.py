import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_device
from app.database import get_db
from app.models import Device
from app.schemas import ClearHistoryResponse, MemoryHistoryResponse
from app.services.memory_service import clear_history, get_history

logger = logging.getLogger("trady.memory")
router = APIRouter()


@router.get("/history", response_model=MemoryHistoryResponse)
async def get_memory_history(
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> MemoryHistoryResponse:
    logger.info(f"[Memory] History request from {device.device_id}")
    items = await get_history(db, device.device_id)
    logger.info(f"[Memory] Returning {len(items)} items")
    return MemoryHistoryResponse(items=items)


@router.delete("/history", response_model=ClearHistoryResponse)
async def clear_memory_history(
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> ClearHistoryResponse:
    logger.info(f"[Memory] Clear history request from {device.device_id}")
    await clear_history(db, device.device_id)
    return ClearHistoryResponse(success=True)
