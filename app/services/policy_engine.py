"""
Command policy engine.

Policy is enforced HERE — never by LLM output.
Order of precedence: blocked > approval_required > allowed > unknown.
"""
import logging
from enum import Enum

from app.config import settings

logger = logging.getLogger("trady.policy")


class PolicyDecision(str, Enum):
    ALLOWED = "allowed"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


def evaluate(command: str, mode: str = "paper") -> PolicyDecision:
    """
    Return the policy decision for a command.

    - Live mode commands that are in the approval list are still APPROVAL_REQUIRED.
    - Risk-increasing commands always require approval regardless of mode.
    - Blocked commands are always rejected.
    """
    cmd = command.strip().lower()

    if cmd in settings.blocked_commands_set:
        logger.warning(f"[Policy] BLOCKED command attempted: {cmd!r}")
        return PolicyDecision.BLOCKED

    # Any command in approval set is approval-required regardless of mode
    if cmd in settings.approval_commands_set:
        logger.info(f"[Policy] APPROVAL_REQUIRED: {cmd!r} mode={mode}")
        return PolicyDecision.APPROVAL_REQUIRED

    # Live mode: anything not explicitly in allowed list also requires approval
    if mode == "live" and cmd not in settings.allowed_commands_set:
        logger.info(f"[Policy] APPROVAL_REQUIRED (live mode): {cmd!r}")
        return PolicyDecision.APPROVAL_REQUIRED

    if cmd in settings.allowed_commands_set:
        logger.info(f"[Policy] ALLOWED: {cmd!r}")
        return PolicyDecision.ALLOWED

    logger.warning(f"[Policy] UNKNOWN command: {cmd!r}")
    return PolicyDecision.UNKNOWN
