from fastapi import APIRouter

from app.seed.kim_jichul import load_seed_transactions

router = APIRouter(prefix="/seed", tags=["seed"])


@router.get("/transactions")
async def seed_transactions() -> list[dict]:
    return load_seed_transactions()
