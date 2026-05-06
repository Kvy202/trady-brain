import logging

from app.schemas import VoiceAction, VoiceTurnResponse
from app.services.trading_supervisor import get_demo_status

logger = logging.getLogger("trady.command_router")


def _detect_intent(text: str) -> str:
    t = text.lower().strip()

    if any(k in t for k in ["bot status", "trading status", "how is my bot", "what is my bot", "bot doing"]):
        return "bot_status"
    if any(k in t for k in ["pnl", "profit", "loss", "return", "show pnl", "performance"]):
        return "show_pnl"
    if any(k in t for k in ["pause bot", "pause trading", "stop bot"]):
        return "pause_bot"
    if any(k in t for k in ["resume bot", "resume trading", "unpause", "start bot"]):
        return "resume_bot"
    if any(k in t for k in ["reduce risk", "lower risk", "less risk"]):
        return "reduce_risk"
    if any(k in t for k in ["conservative", "safe mode", "conservative mode"]):
        return "conservative_mode"
    if any(k in t for k in ["emergency stop", "stop everything", "halt all"]):
        return "emergency_stop_demo"
    if any(k in t for k in ["hello", "hi ", "hey ", "good morning", "good evening", "how are you"]):
        return "greeting"
    if any(k in t for k in ["who are you", "what are you", "what can you do", "help", "capabilities"]):
        return "capabilities"

    return "unknown"


async def route_command(text: str, device_id: str) -> VoiceTurnResponse:
    logger.debug(f"[CommandRouter] Routing '{text}' from {device_id}")
    intent = _detect_intent(text)
    logger.info(f"[CommandRouter] Intent detected: {intent}")

    if intent == "bot_status":
        s = get_demo_status()
        reply = (
            f"Trading bot is {'online' if s.online else 'offline'}. "
            f"Demo PnL is +{s.pnlDay}%. Risk mode is {s.riskMode}. "
            f"Drawdown is {s.drawdown}%."
        )
        return VoiceTurnResponse(
            reply=reply,
            intent=intent,
            requiresApproval=False,
            actions=[VoiceAction(
                type="trading_status",
                label="Demo bot status",
                data={"online": s.online, "pnlDay": s.pnlDay, "riskMode": s.riskMode, "drawdown": s.drawdown},
            )],
        )

    if intent == "show_pnl":
        s = get_demo_status()
        return VoiceTurnResponse(
            reply=f"Demo PnL for today is +{s.pnlDay}%. This is a simulation only.",
            intent=intent,
            requiresApproval=False,
            actions=[VoiceAction(type="pnl_data", label="Demo PnL", data={"pnlDay": s.pnlDay})],
        )

    if intent == "pause_bot":
        return VoiceTurnResponse(
            reply="Demo bot has been paused. No real trades are affected.",
            intent=intent,
            requiresApproval=False,
            actions=[VoiceAction(type="bot_command", label="Pause demo bot", data={"command": "pause_bot"})],
        )

    if intent == "resume_bot":
        return VoiceTurnResponse(
            reply="Resuming the bot requires your approval. Please confirm in the app.",
            intent=intent,
            requiresApproval=True,
            actions=[VoiceAction(
                type="approval_required",
                label="Resume bot — approval needed",
                data={"command": "resume_bot"},
            )],
        )

    if intent == "reduce_risk":
        return VoiceTurnResponse(
            reply="Demo risk level has been reduced to conservative settings.",
            intent=intent,
            requiresApproval=False,
            actions=[VoiceAction(type="bot_command", label="Reduce risk", data={"command": "reduce_risk"})],
        )

    if intent == "conservative_mode":
        return VoiceTurnResponse(
            reply="Demo bot switched to conservative mode. Position sizing reduced.",
            intent=intent,
            requiresApproval=False,
            actions=[VoiceAction(type="bot_command", label="Conservative mode", data={"command": "conservative_mode"})],
        )

    if intent == "emergency_stop_demo":
        return VoiceTurnResponse(
            reply="Emergency stop on the demo bot requires your explicit approval. This will halt all demo activity.",
            intent=intent,
            requiresApproval=True,
            actions=[VoiceAction(
                type="approval_required",
                label="Emergency stop — approval needed",
                data={"command": "emergency_stop_demo"},
            )],
        )

    if intent == "greeting":
        return VoiceTurnResponse(
            reply="Hello! I'm Trady, your AI trading assistant. Phase 2 backend is connected and ready.",
            intent=intent,
            requiresApproval=False,
        )

    if intent == "capabilities":
        return VoiceTurnResponse(
            reply=(
                "I can help with: bot status, demo PnL, pausing the demo bot, "
                "reducing risk, switching to conservative mode, and emergency stop demo."
            ),
            intent=intent,
            requiresApproval=False,
        )

    # unknown
    return VoiceTurnResponse(
        reply=(
            "I heard you. Phase 2 backend is connected. "
            "I can currently handle: bot status, demo PnL, pause demo bot, "
            "reduce risk, and conservative mode."
        ),
        intent="unknown",
        requiresApproval=False,
    )
