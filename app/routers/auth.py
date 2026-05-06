import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, create_refresh_token
from app.config import settings
from app.database import get_db
from app.models import Device
from app.schemas import DeviceAuthRequest, DeviceAuthResponse

logger = logging.getLogger("trady.auth.router")
router = APIRouter()


@router.post("/device", response_model=DeviceAuthResponse)
async def device_auth(request: DeviceAuthRequest, db: AsyncSession = Depends(get_db)) -> DeviceAuthResponse:
    logger.info(f"[Auth] Device auth: id={request.deviceId} name={request.deviceName}")

    result = await db.execute(select(Device).where(Device.device_id == request.deviceId))
    device = result.scalar_one_or_none()

    if device is None:
        device = Device(device_id=request.deviceId, device_name=request.deviceName)
        db.add(device)
        logger.info(f"[Auth] New device registered: {request.deviceId}")
    else:
        device.device_name = request.deviceName
        logger.info(f"[Auth] Existing device re-authenticated: {request.deviceId}")

    access_token = create_access_token(request.deviceId)
    refresh_token = create_refresh_token(request.deviceId)
    device.refresh_token = refresh_token

    await db.commit()
    logger.info(f"[Auth] Tokens issued for: {request.deviceId}")

    return DeviceAuthResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        tokenType="bearer",
        expiresIn=settings.jwt_access_expire_minutes * 60,
    )
