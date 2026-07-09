"""일회성 백필: merchant_normalized가 비어 있는(NULL) 기존 거래를 채운다.

신규 업로드는 insert 경로에서 자동으로 채워지므로, 이 스크립트는 이 기능 배포
'이전'에 쌓인 거래에만 필요하다. 한 번만 실행하면 된다(멱등 — NULL만 대상).

Usage:
    cd apps/api && uv run python ../../scripts/backfill_merchant_normalized.py
"""
import asyncio
import os
import sys

# apps/api에서 실행될 때 app.* 를 import 하기 위해 cwd를 path에 추가
sys.path.insert(0, os.getcwd())

import asyncpg  # noqa: E402

from app.categorization.merchant import normalize_merchant  # noqa: E402
from app.settings import settings  # noqa: E402


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        rows = await conn.fetch(
            "SELECT id, merchant_raw FROM transactions WHERE merchant_normalized IS NULL"
        )
        print(f"backfill 대상(merchant_normalized IS NULL): {len(rows)}건")
        updated = 0
        for r in rows:
            norm = normalize_merchant(r["merchant_raw"] or "")
            await conn.execute(
                "UPDATE transactions SET merchant_normalized = $2 WHERE id = $1",
                r["id"], norm,
            )
            updated += 1
        print(f"완료: {updated}건 갱신")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
