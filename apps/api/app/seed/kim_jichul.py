import json
from pathlib import Path
from typing import Any

# apps/api 안에 seed/ 두어 Docker 빌드 컨텍스트에 포함되도록 함.
# parents[0]=app/seed/, parents[1]=app/, parents[2]=apps/api/ (= Docker WORKDIR /app)
_DATA_PATH = Path(__file__).resolve().parents[2] / "seed" / "kim_jichul" / "transactions.json"


def load_seed_transactions() -> list[dict[str, Any]]:
    """Load 김지출 seed transactions for guest mode. No DB."""
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
