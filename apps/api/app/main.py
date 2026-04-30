from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_pool, close_pool
from app.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("spendlens")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    # seed_admin_user는 Task 14에서 추가
    logger.info("startup complete")
    yield
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


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
