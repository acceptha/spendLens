from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-ess-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _txn(conn, email, *, category):
    u = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    row = await conn.fetchrow(
        """
        INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row)
        VALUES ($1,'test',CURRENT_DATE,1000,'M',$2,$3,'{}'::jsonb) RETURNING id
        """,
        u["id"], category, str(uuid4()),
    )
    return row["id"]


async def test_effective_essential_derived_from_category(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            await _txn(conn, email, category="housing")   # 기본 필수
            await _txn(conn, email, category="coffee")    # 기본 비필수

        r = await ac.get("/transactions", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        by_cat = {t["effective_category"]: t for t in r.json()}
        assert by_cat["housing"]["effective_essential"] is True
        assert by_cat["housing"]["essential_override"] is None
        assert by_cat["coffee"]["effective_essential"] is False
