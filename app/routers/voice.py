import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_device
from app.database import get_db
from app.models import Device
from app.schemas import VoiceTurnRequest, VoiceTurnResponse
from app.services.command_router import route_command
from app.services.memory_service import save_turn

logger = logging.getLogger("trady.voice")
router = APIRouter()


@router.post("/turn", response_model=VoiceTurnResponse)
async def voice_turn(
    request: VoiceTurnRequest,
    device: Device = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> VoiceTurnResponse:
    logger.info(f"[Voice] Turn from {device.device_id}: text='{request.text}' lang={request.lang}")

    response = await route_command(request.text, device.device_id)

    await save_turn(db, device.device_id, "user", request.text, response.intent)
    await save_turn(db, device.device_id, "assistant", response.reply, response.intent)

    logger.info(
        f"[Voice] Reply: intent={response.intent} "
        f"requiresApproval={response.requiresApproval} "
        f"reply='{response.reply[:80]}'"
    )
    return response
