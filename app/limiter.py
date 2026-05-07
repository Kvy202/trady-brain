"""
Rate limiter singleton.

Imported by both main.py (registers with app.state) and
routers/trading.py (applies @limiter.limit decorator).
Using a shared module avoids circular imports.
"""
import hashlib

from fastapi import Request
from slowapi import Limiter


def _device_key(request: Request) -> str:
    """Per-device key: hash of the Bearer token, or IP fallback."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return "tok:" + hashlib.sha256(token.encode()).hexdigest()[:32]
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_device_key)
