"""
Demo-only trading supervisor.

NO real trading. NO real exchange connections. NO real orders.
All state is in-memory and resets on restart.
Commands that could cause significant state change (resume, emergency stop)
require explicit approval — they are flagged requiresApproval=True and
no state change is applied until the user confirms.
"""
import logging

from app.schemas import TradingCommandResponse, TradingPosition, TradingStatusResponse

logger = logging.getLogger("trady.trading_supervisor")

# ── In-memory demo state ──────────────────────────────────────────────────────
_state: dict = {
    "online": True,
    "mode": "demo",
    "pnlDay": 0.7,
    "riskMode": "medium",
    "drawdown": 0.3,
    "positions": [
        {"symbol": "BTCUSDT", "side": "long",  "size": "demo-small", "pnl": 0.4},
        {"symbol": "ETHUSDT", "side": "long",  "size": "demo-micro", "pnl": 0.3},
    ],
}

# Commands that block on approval before any state change
_REQUIRES_APPROVAL = {"resume_bot", "emergency_stop_demo"}

_MESSAGES = {
    "bot_status":          "Demo bot status retrieved.",
    "pause_bot":           "Demo bot paused. No real trades affected.",
    "resume_bot":          "Resume requires approval. Confirm in app to proceed.",
    "reduce_risk":         "Demo risk level reduced to low.",
    "conservative_mode":   "Demo bot switched to conservative mode.",
    "emergency_stop_demo": "Emergency stop requires explicit approval. Confirm in app.",
}


def get_demo_status() -> TradingStatusResponse:
    logger.debug(f"[TradingSupervisor] Returning demo status: {_state['riskMode']} pnl={_state['pnlDay']}")
    return TradingStatusResponse(
        online=_state["online"],
        mode=_state["mode"],
        pnlDay=_state["pnlDay"],
        riskMode=_state["riskMode"],
        drawdown=_state["drawdown"],
        positions=[TradingPosition(**p) for p in _state["positions"]],
    )


def execute_demo_command(command: str, reason: str) -> TradingCommandResponse:
    logger.info(f"[TradingSupervisor] Command: {command!r} reason={reason!r}")

    requires_approval = command in _REQUIRES_APPROVAL
    known = command in _MESSAGES
    message = _MESSAGES.get(command, f"Unknown demo command: {command!r}")

    # Only apply state change for safe commands that don't need approval
    if known and not requires_approval:
        _apply_state_change(command)

    result = TradingCommandResponse(
        success=known,
        command=command,
        requiresApproval=requires_approval,
        message=message,
    )
    logger.info(f"[TradingSupervisor] Result: {result.success=} {result.requiresApproval=}")
    return result


def _apply_state_change(command: str) -> None:
    if command == "pause_bot":
        _state["online"] = False
        logger.info("[TradingSupervisor] Demo bot set offline")
    elif command == "reduce_risk":
        _state["riskMode"] = "low"
        logger.info("[TradingSupervisor] Demo risk → low")
    elif command == "conservative_mode":
        _state["riskMode"] = "conservative"
        logger.info("[TradingSupervisor] Demo risk → conservative")
