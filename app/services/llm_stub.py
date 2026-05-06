# Phase 2 uses a rule-based command router (command_router.py).
# Replace with Claude API or another LLM in Phase 3.
import logging

logger = logging.getLogger("trady.llm_stub")


def generate_stub(prompt: str) -> str:
    logger.debug(f"[LLMStub] Would generate for: '{prompt[:60]}'")
    return f"[LLM Phase 3] {prompt[:60]}"
