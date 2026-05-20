import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.auth.seed import ensure_admin_user
from app.dashboard.routes import router as dashboard_router
from app.db import acquire, close_pool, init_pool
from app.redis_client import close_redis, init_redis
from app.seed.routes import router as seed_router
from app.settings import settings
from app.transactions.routes import router as transactions_router

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("spendlens")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    await init_redis()
    async with acquire() as conn:
        await ensure_admin_user(conn)
    logger.info("startup complete; admin seeded; redis ready")
    yield
    await close_redis()
    await close_pool()
    logger.info("shutdown complete")


app = FastAPI(title="spendLens API", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(seed_router)
app.include_router(transactions_router)
app.include_router(dashboard_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
