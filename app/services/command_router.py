"""
Voice command router — phrase normalisation, intent classification,
and safe dispatch to bot_client / policy engine.

Intent precedence:
  blocked_dangerous > trading_query > safe_command > approval_required
  > android_control > greeting > unknown
"""
import logging

from app.schemas import VoiceAction, VoiceTurnResponse
from app.services import bot_client
from app.services.bot_client import BotUnavailableError
from app.services.policy_engine import PolicyDecision, evaluate

logger = logging.getLogger("trady.command_router")

# ── Wake phrase stripping ─────────────────────────────────────────────────────

_WAKE_PREFIXES = [
    "hey trady,", "hello trady,", "trady,", "wake up trady,",
    "trady listen,", "trady listen", "hey trady", "hello trady", "wake up trady",
]


def _strip_wake(text: str) -> str:
    t = text.strip().lower()
    for prefix in _WAKE_PREFIXES:
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
            break
    return t


# ── Intent detection ──────────────────────────────────────────────────────────

def _detect_intent(t: str) -> str:
    """Map normalised (lowercased, wake-stripped) text to an intent name."""
    if not t:
        return "GREETING"

    # Blocked dangerous — reject before everything else
    if any(k in t for k in [
        "withdraw funds", "transfer funds", "reveal api", "show api key",
        "show exchange api", "disable all safety", "remove stop loss",
        "set unlimited leverage", "bypass risk", "bypass safety",
        "disable safety", "disable stop loss",
    ]):
        return "BLOCKED_DANGEROUS_COMMAND"

    # ── Trading queries ───────────────────────────────────────────────────────
    if any(k in t for k in [
        "bot status", "bot doing", "how is my bot", "what is my bot",
        "is my bot", "is the trading bot", "bot active", "bot running",
        "trading bot active", "trading bot running", "check trading status",
        "show bot status", "what is the bot",
    ]):
        return "BOT_STATUS"

    if any(k in t for k in [
        "pnl", "profit and loss", "show pnl", "today's pnl",
        "today pnl", "how much profit", "how much loss",
        "show today's pnl", "what is my pnl",
    ]):
        return "BOT_PNL"

    if any(k in t for k in [
        "open positions", "my positions", "show positions", "what positions",
        "positions are open", "position open", "show my open positions",
        "what positions are open",
    ]):
        return "BOT_POSITIONS"

    if any(k in t for k in [
        "bot logs", "show logs", "trading logs", "bot log",
        "why did the bot", "what did the bot do",
    ]):
        return "BOT_LOGS"

    if any(k in t for k in [
        "risk level", "risk mode", "bot risk", "show risk",
        "what is the risk", "current risk", "show bot risk",
    ]):
        return "BOT_RISK"

    if any(k in t for k in [
        "summarize today", "trading summary", "today's trading",
        "summary of trading", "summarize trading",
    ]):
        return "BOT_TRADING_SUMMARY"

    # ── Safe trading commands (ALLOWED by policy) ─────────────────────────────
    if any(k in t for k in [
        "pause the bot", "pause bot", "pause trading",
        "stop the bot for now", "stop bot",
    ]):
        return "PAUSE_BOT"

    if any(k in t for k in [
        "reduce risk", "lower risk", "less risk",
        "lower exposure", "reduce exposure",
    ]):
        return "REDUCE_RISK"

    if any(k in t for k in [
        "conservative mode", "conservative", "safe mode",
        "switch to conservative", "paper mode", "switch to paper",
    ]):
        return "CONSERVATIVE_MODE"

    # ── Approval-required commands ────────────────────────────────────────────
    if any(k in t for k in [
        "resume the bot", "resume bot", "resume trading",
        "resume live", "resume live trading", "unpause", "start bot",
        "start the bot",
    ]):
        return "RESUME_BOT"

    if any(k in t for k in [
        "emergency stop", "stop everything", "halt all", "emergency halt",
    ]):
        return "EMERGENCY_STOP"

    if any(k in t for k in [
        "close all positions", "flatten positions", "flatten all",
        "close positions", "close all",
    ]):
        return "FLATTEN_POSITIONS"

    if any(k in t for k in [
        "increase risk", "more risk", "higher risk",
        "increase exposure", "higher leverage",
    ]):
        return "INCREASE_RISK"

    if any(k in t for k in ["change strategy", "new strategy", "switch strategy"]):
        return "CHANGE_STRATEGY"

    if any(k in t for k in [
        "add symbol", "add new symbol", "trade a new pair",
        "new pair", "add pair", "add a new trading pair",
    ]):
        return "ADD_SYMBOL"

    # ── Android control ───────────────────────────────────────────────────────
    if any(k in t for k in [
        "open trading dashboard", "trading dashboard",
        "show dashboard", "open dashboard",
    ]):
        return "OPEN_TRADING_DASHBOARD"

    if "open binance" in t:
        return "OPEN_APP"

    if "open tradingview" in t or "trading view" in t:
        return "OPEN_APP"

    if any(k in t for k in [
        "open whatsapp", "whatsapp to message", "send whatsapp",
        "message via whatsapp",
    ]):
        return "OPEN_WHATSAPP"

    # call check before maps to avoid "call navigate" style false matches
    if t.startswith("call "):
        return "CALL_CONTACT"

    if any(k in t for k in [
        "open maps", "navigate home", "navigate to", "google maps",
    ]):
        return "OPEN_MAPS"

    if any(k in t for k in [
        "set alarm", "create an alarm", "alarm for",
        "create alarm", "alarm at",
    ]):
        return "CREATE_ALARM"

    if any(k in t for k in [
        "remind me", "add reminder", "set reminder",
        "add daily review", "reminder for",
    ]):
        return "CREATE_REMINDER"

    if any(k in t for k in [
        "show tasks", "today's tasks", "my tasks",
        "what are my tasks", "show today's tasks",
    ]):
        return "SHOW_TASKS"

    if any(k in t for k in [
        "show my schedule", "my schedule", "show schedule",
        "what's my schedule", "what is my schedule",
    ]):
        return "SHOW_SCHEDULE"

    if any(k in t for k in [
        "notify me if", "call me if", "alert me when",
        "send push notification", "tell me if",
        "notify me when", "alert when",
    ]):
        return "SET_ALERT"

    # ── Greeting / capabilities ───────────────────────────────────────────────
    if any(k in t for k in [
        "good morning", "good evening", "good afternoon", "how are you",
    ]) or t in ("hello", "hi", "hey"):
        return "GREETING"

    if any(k in t for k in [
        "who are you", "what are you", "what can you do",
        "help", "capabilities",
    ]):
        return "CAPABILITIES"

    return "UNKNOWN"


# ── Intent → command / message maps ──────────────────────────────────────────

_ALLOWED_INTENT_TO_COMMAND: dict = {
    "PAUSE_BOT":         "pause_bot",
    "REDUCE_RISK":       "reduce_risk",
    "CONSERVATIVE_MODE": "conservative_mode",
}

_APPROVAL_INTENT_TO_COMMAND: dict = {
    "RESUME_BOT":        "resume_bot",
    "EMERGENCY_STOP":    "emergency_stop",
    "FLATTEN_POSITIONS": "flatten_positions",
    "INCREASE_RISK":     "increase_risk",
    "CHANGE_STRATEGY":   "change_strategy",
    "ADD_SYMBOL":        "add_symbol",
}

_APPROVAL_MESSAGES: dict = {
    "RESUME_BOT":        "Resuming live trading requires your explicit approval. Open the Trading Dashboard to confirm.",
    "EMERGENCY_STOP":    "Emergency stop requires your explicit approval. Open the Trading Dashboard to confirm.",
    "FLATTEN_POSITIONS": "Closing all positions requires your explicit approval. Open the Trading Dashboard to confirm.",
    "INCREASE_RISK":     "Increasing risk requires your explicit approval. Open the Trading Dashboard to confirm.",
    "CHANGE_STRATEGY":   "Changing strategy requires your explicit approval. Open the Trading Dashboard to confirm.",
    "ADD_SYMBOL":        "Adding a new trading symbol requires your explicit approval. Open the Trading Dashboard to confirm.",
}

_BLOCKED_REPLY = (
    "I cannot do that. Trady is only a supervisor and cannot "
    "withdraw funds, reveal keys, or bypass trading safety."
)


# ── Route dispatcher ──────────────────────────────────────────────────────────

async def route_command(text: str, device_id: str) -> VoiceTurnResponse:
    stripped = _strip_wake(text)
    intent = _detect_intent(stripped)
    logger.info(
        f"[CommandRouter] device={device_id} "
        f"stripped='{stripped[:60]}' intent={intent}"
    )

    # ── Blocked dangerous ─────────────────────────────────────────────────────
    if intent == "BLOCKED_DANGEROUS_COMMAND":
        logger.warning(f"[CommandRouter] Blocked dangerous phrase from {device_id}: '{stripped[:60]}'")
        return VoiceTurnResponse(reply=_BLOCKED_REPLY, intent=intent, requiresApproval=False)

    # ── Trading queries ───────────────────────────────────────────────────────
    if intent == "BOT_STATUS":
        try:
            data = await bot_client.get_status()
            online = "online" if data.get("online") else "offline"
            reply = (
                f"Your bot is {online}. "
                f"Today's PnL: {data.get('pnlDay', 0):+.2f}%. "
                f"Risk mode: {data.get('riskMode', 'unknown')}. "
                f"Drawdown: {data.get('drawdown', 0):.2f}%."
            )
            return VoiceTurnResponse(
                reply=reply, intent=intent, requiresApproval=False,
                actions=[VoiceAction(
                    type="trading_status", label="Bot status",
                    data={k: data.get(k) for k in ("online", "pnlDay", "riskMode", "drawdown")},
                )],
            )
        except BotUnavailableError:
            logger.warning(f"[CommandRouter] Bot unavailable for {intent}")
            return VoiceTurnResponse(
                reply="The trading bot is currently unreachable. Please check your connection.",
                intent=intent, requiresApproval=False,
            )

    if intent == "BOT_PNL":
        try:
            data = await bot_client.get_metrics()
            reply = (
                f"Today's PnL: {data.get('pnlDay', 0):+.2f}%. "
                f"This week: {data.get('pnlWeek', 0):+.2f}%. "
                f"Win rate: {data.get('winRate', 0) * 100:.0f}%."
            )
            return VoiceTurnResponse(
                reply=reply, intent=intent, requiresApproval=False,
                actions=[VoiceAction(type="pnl_data", label="PnL metrics", data={
                    "pnlDay": data.get("pnlDay"),
                    "pnlWeek": data.get("pnlWeek"),
                    "winRate": data.get("winRate"),
                })],
            )
        except BotUnavailableError:
            return VoiceTurnResponse(
                reply="PnL data is unavailable right now. The trading bot is unreachable.",
                intent=intent, requiresApproval=False,
            )

    if intent == "BOT_POSITIONS":
        try:
            data = await bot_client.get_positions()
            positions = data.get("positions", [])
            if positions:
                pos_text = ", ".join(
                    f"{p.get('symbol', '?')} {p.get('side', '?')}" for p in positions[:4]
                )
                reply = (
                    f"Open positions: {pos_text}. "
                    f"Total exposure: {data.get('totalExposure', 0):.0f}."
                )
            else:
                reply = "No open positions at the moment."
            return VoiceTurnResponse(
                reply=reply, intent=intent, requiresApproval=False,
                actions=[VoiceAction(type="positions_data", label="Open positions", data={
                    "positions": positions,
                    "totalExposure": data.get("totalExposure"),
                })],
            )
        except BotUnavailableError:
            return VoiceTurnResponse(
                reply="Position data is unavailable. The trading bot is unreachable.",
                intent=intent, requiresApproval=False,
            )

    if intent == "BOT_LOGS":
        try:
            data = await bot_client.get_logs()
            logs = data.get("logs", [])
            recent = logs[-3:] if logs else []
            if recent:
                last = recent[-1]
                reply = (
                    f"Last log: [{last.get('level', '?')}] {last.get('message', '')}. "
                    f"Total recent entries: {len(logs)}."
                )
            else:
                reply = "No recent log entries."
            return VoiceTurnResponse(
                reply=reply, intent=intent, requiresApproval=False,
                actions=[VoiceAction(type="logs_data", label="Bot logs", data={"logs": recent})],
            )
        except BotUnavailableError:
            return VoiceTurnResponse(
                reply="Log data is unavailable. The trading bot is unreachable.",
                intent=intent, requiresApproval=False,
            )

    if intent == "BOT_RISK":
        try:
            data = await bot_client.get_status()
            reply = (
                f"Current risk mode: {data.get('riskMode', 'unknown')}. "
                f"Drawdown: {data.get('drawdown', 0):.2f}%."
            )
            return VoiceTurnResponse(
                reply=reply, intent=intent, requiresApproval=False,
                actions=[VoiceAction(type="risk_data", label="Bot risk", data={
                    "riskMode": data.get("riskMode"),
                    "drawdown": data.get("drawdown"),
                })],
            )
        except BotUnavailableError:
            return VoiceTurnResponse(
                reply="Risk data is unavailable. The trading bot is unreachable.",
                intent=intent, requiresApproval=False,
            )

    if intent == "BOT_TRADING_SUMMARY":
        try:
            status = await bot_client.get_status()
            metrics = await bot_client.get_metrics()
            reply = (
                f"Today's summary: Bot is {'online' if status.get('online') else 'offline'}. "
                f"PnL: {metrics.get('pnlDay', 0):+.2f}%. "
                f"Trades: {metrics.get('totalTrades', 0)}. "
                f"Win rate: {metrics.get('winRate', 0) * 100:.0f}%. "
                f"Risk: {status.get('riskMode', 'unknown')}."
            )
            return VoiceTurnResponse(
                reply=reply, intent=intent, requiresApproval=False,
                actions=[VoiceAction(type="trading_summary", label="Daily summary", data={
                    "pnlDay": metrics.get("pnlDay"),
                    "totalTrades": metrics.get("totalTrades"),
                    "winRate": metrics.get("winRate"),
                    "riskMode": status.get("riskMode"),
                })],
            )
        except BotUnavailableError:
            return VoiceTurnResponse(
                reply="Trading summary unavailable. The trading bot is unreachable.",
                intent=intent, requiresApproval=False,
            )

    # ── Safe trading commands — execute via policy + bot_client ───────────────
    if intent in _ALLOWED_INTENT_TO_COMMAND:
        command = _ALLOWED_INTENT_TO_COMMAND[intent]
        decision = evaluate(command)
        if decision == PolicyDecision.ALLOWED:
            try:
                result = await bot_client.send_command(command, "voice command", "paper")
                return VoiceTurnResponse(
                    reply=result.get("message", f"Command '{command}' executed successfully."),
                    intent=intent, requiresApproval=False,
                    actions=[VoiceAction(type="bot_command", label=command, data={"command": command})],
                )
            except BotUnavailableError:
                return VoiceTurnResponse(
                    reply="Command could not be sent. The trading bot is currently unreachable.",
                    intent=intent, requiresApproval=False,
                )
        return VoiceTurnResponse(
            reply=f"Command '{command}' cannot be executed right now.",
            intent=intent, requiresApproval=False,
        )

    # ── Approval-required commands ────────────────────────────────────────────
    if intent in _APPROVAL_INTENT_TO_COMMAND:
        message = _APPROVAL_MESSAGES.get(intent, "This action requires your explicit approval.")
        command = _APPROVAL_INTENT_TO_COMMAND[intent]
        return VoiceTurnResponse(
            reply=message, intent=intent, requiresApproval=True,
            actions=[VoiceAction(
                type="approval_required",
                label=f"{intent} — approval needed",
                data={"command": command, "route": "trading_dashboard"},
            )],
        )

    # ── Android control ───────────────────────────────────────────────────────
    if intent == "OPEN_TRADING_DASHBOARD":
        return VoiceTurnResponse(
            reply="Opening Trading Dashboard.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="navigate", label="Trading Dashboard", data={"route": "trading_dashboard"})],
        )

    if intent == "OPEN_APP":
        if "binance" in stripped:
            pkg, name = "com.binance.dev", "Binance"
        elif "tradingview" in stripped or "trading view" in stripped:
            pkg, name = "com.tradingview.tradingviewapp", "TradingView"
        else:
            pkg, name = "", stripped
        return VoiceTurnResponse(
            reply=f"Opening {name}.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="open_app", label=f"Open {name}", data={"packageName": pkg, "displayName": name})],
        )

    if intent == "OPEN_WHATSAPP":
        return VoiceTurnResponse(
            reply="Opening WhatsApp.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="open_app", label="Open WhatsApp", data={"packageName": "com.whatsapp", "displayName": "WhatsApp"})],
        )

    if intent == "OPEN_MAPS":
        query = ""
        if "navigate home" in stripped:
            query = "home"
        elif "navigate to" in stripped:
            query = stripped.split("navigate to", 1)[-1].strip()
        return VoiceTurnResponse(
            reply="Opening Google Maps.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="open_maps", label="Open Maps", data={"query": query})],
        )

    if intent == "CALL_CONTACT":
        contact = stripped.removeprefix("call ").strip()
        return VoiceTurnResponse(
            reply=f"Calling {contact}.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="call", label=f"Call {contact}", data={"contact": contact})],
        )

    if intent == "CREATE_ALARM":
        return VoiceTurnResponse(
            reply="I'll open the alarm for you. Voice alarm creation is handled on your device.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="create_alarm", label="Create Alarm", data={})],
        )

    if intent == "CREATE_REMINDER":
        return VoiceTurnResponse(
            reply="I'll help you set a reminder. Reminder creation is handled on your device.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="create_reminder", label="Create Reminder", data={})],
        )

    if intent == "SHOW_TASKS":
        return VoiceTurnResponse(
            reply="Opening your tasks. Task management is handled on your device.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="show_tasks", label="Show Tasks", data={})],
        )

    if intent == "SHOW_SCHEDULE":
        return VoiceTurnResponse(
            reply="Opening your schedule. Calendar is handled on your device.",
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="show_schedule", label="Show Schedule", data={})],
        )

    if intent == "SET_ALERT":
        return VoiceTurnResponse(
            reply=(
                "Alert configuration is available in the Trading Dashboard. "
                "You can set drawdown alerts and bot event notifications there."
            ),
            intent=intent, requiresApproval=False,
            actions=[VoiceAction(type="set_alert", label="Set Alert", data={"route": "trading_dashboard"})],
        )

    # ── Greeting / capabilities ───────────────────────────────────────────────
    if intent == "GREETING":
        return VoiceTurnResponse(
            reply=(
                "Hello! I'm Trady, your AI trading supervisor. "
                "I can check bot status, execute safe commands, and alert you before risky actions. "
                "How can I help?"
            ),
            intent=intent, requiresApproval=False,
        )

    if intent == "CAPABILITIES":
        return VoiceTurnResponse(
            reply=(
                "I can help with: bot status, PnL, open positions, bot logs, "
                "pause bot, reduce risk, conservative mode. "
                "Riskier actions like resume trading or emergency stop need your approval. "
                "I can also open apps, navigate, set alarms, and more."
            ),
            intent=intent, requiresApproval=False,
        )

    # ── Unknown ───────────────────────────────────────────────────────────────
    return VoiceTurnResponse(
        reply=(
            "I'm not sure how to handle that. "
            "Try: 'bot status', 'pause bot', 'show positions', 'open Binance', "
            "or say 'what can you do' for a full list."
        ),
        intent="UNKNOWN",
        requiresApproval=False,
    )
