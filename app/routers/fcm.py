import logging

from fastapi import APIRouter, Depends

from app.auth import get_current_device
from app.models import Device
from app.schemas import FcmTestRequest, FcmTestResponse
from app.services.fcm_service import prepare_demo_payload

logger = logging.getLogger("trady.fcm")
router = APIRouter()


@router.post("/test", response_model=FcmTestResponse)
async def fcm_test(
    request: FcmTestRequest,
    device: Device = Depends(get_current_device),
) -> FcmTestResponse:
    logger.info(f"[FCM] Test from {device.device_id}: type={request.type}")
    result = prepare_demo_payload(request)
    logger.info(f"[FCM] Payload prepared: success={result.success}")
    return result
