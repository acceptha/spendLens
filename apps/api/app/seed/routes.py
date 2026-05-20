from uuid import uuid4

from fastapi import APIRouter

from app.seed.kim_jichul import load_seed_transactions

router = APIRouter(prefix="/seed", tags=["seed"])


@router.get("/transactions")
async def seed_transactions() -> list[dict]:
    # W3: TransactionRow shape으로 정렬 — id + auto/override/effective category fields 주입
    txns = load_seed_transactions()
    for t in txns:
        t.setdefault("id", str(uuid4()))
        t.setdefault("auto_category", t.get("category", "unknown"))
        t.setdefault("user_category_override", None)
        t.setdefault("effective_category", t.get("category", "unknown"))
    return txns
