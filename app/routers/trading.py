import logging

from fastapi import APIRouter, Depends

from app.auth import get_current_device
from app.models import Device
from app.schemas import TradingCommandRequest, TradingCommandResponse, TradingStatusResponse
from app.services.trading_supervisor import execute_demo_command, get_demo_status

logger = logging.getLogger("trady.trading")
router = APIRouter()


@router.get("/status", response_model=TradingStatusResponse)
async def trading_status(device: Device = Depends(get_current_device)) -> TradingStatusResponse:
    logger.info(f"[Trading] Status request from {device.device_id}")
    status = get_demo_status()
    logger.info(f"[Trading] Demo: online={status.online} pnl={status.pnlDay} risk={status.riskMode}")
    return status


@router.post("/command", response_model=TradingCommandResponse)
async def trading_command(
    request: TradingCommandRequest,
    device: Device = Depends(get_current_device),
) -> TradingCommandResponse:
    logger.info(f"[Trading] Command from {device.device_id}: {request.command} reason='{request.reason}'")
    result = execute_demo_command(request.command, request.reason or "")
    logger.info(f"[Trading] Result: success={result.success} requiresApproval={result.requiresApproval}")
    return result
