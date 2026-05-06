import logging

from app.config import settings
from app.schemas import FcmTestRequest, FcmTestResponse

logger = logging.getLogger("trady.fcm_service")


def prepare_demo_payload(request: FcmTestRequest) -> FcmTestResponse:
    logger.info(f"[FCMService] Building demo payload type={request.type} title={request.title!r}")

    payload: dict = {
        "notification": {"title": request.title, "body": request.body},
        "data": {"type": request.type, "source": "trady-brain"},
    }

    if request.deviceToken:
        # Token is present — log only that it exists, never log the value
        payload["to"] = request.deviceToken
        logger.debug("[FCMService] Device token present (value not logged)")
    else:
        logger.debug("[FCMService] No device token — demo payload only")

    if settings.fcm_enabled:
        # Firebase Admin SDK integration goes here in Phase 3
        logger.warning("[FCMService] FCM_ENABLED=true but Admin SDK not wired — returning demo payload")

    return FcmTestResponse(success=True, message="Demo FCM payload prepared", payload=payload)
