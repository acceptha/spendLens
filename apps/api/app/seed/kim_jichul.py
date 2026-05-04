import json
from pathlib import Path
from typing import Any

# repo root는 apps/api/app/seed/ 기준 네 단계 위 (parents[4])
# parents[0]=seed/, parents[1]=app/, parents[2]=api/, parents[3]=apps/, parents[4]=spendLens/
_DATA_PATH = Path(__file__).resolve().parents[4] / "seed" / "kim_jichul" / "transactions.json"


def load_seed_transactions() -> list[dict[str, Any]]:
    """Load 김지출 seed transactions for guest mode. No DB."""
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
