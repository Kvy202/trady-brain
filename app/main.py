import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.database import init_db
from app.limiter import limiter
from app.logging_config import setup_logging
from app.routers import auth, fcm, health, memory, trading, voice

logger = logging.getLogger("trady")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"[TradyBrain] Starting {settings.app_name} v{settings.version}")
    logger.info(f"[TradyBrain] Trading bot mode: {settings.trading_bot_mode.upper()}")
    await init_db()
    logger.info("[TradyBrain] Database ready")
    yield
    logger.info("[TradyBrain] Shutdown complete")


app = FastAPI(
    title="Trady Brain",
    version=settings.version,
    description="Trady AI Voice Assistant Backend — Phase 3",
    lifespan=lifespan,
)

# Required by slowapi
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning(f"[RateLimit] Exceeded for {request.client.host if request.client else 'unknown'}")
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many trading commands. Please slow down and retry."},
    )


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router,    prefix="/v1/auth")
app.include_router(voice.router,   prefix="/v1/voice")
app.include_router(memory.router,  prefix="/v1/memory")
app.include_router(trading.router, prefix="/v1/trading")
app.include_router(fcm.router,     prefix="/v1/fcm")
