import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.logging_config import setup_logging
from app.routers import auth, fcm, health, memory, trading, voice

logger = logging.getLogger("trady")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"[TradyBrain] Starting {settings.app_name} v{settings.version}")
    await init_db()
    logger.info("[TradyBrain] Database ready")
    yield
    logger.info("[TradyBrain] Shutdown complete")


app = FastAPI(
    title="Trady Brain",
    version=settings.version,
    description="Trady AI Voice Assistant Backend — Phase 2",
    lifespan=lifespan,
)

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
