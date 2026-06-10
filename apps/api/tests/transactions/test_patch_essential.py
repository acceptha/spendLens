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
    email = f"_w4-pe-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _txn(conn, email, *, category="coffee"):
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


async def test_patch_essential_true_overrides_default(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            tid = await _txn(conn, email, category="coffee")  # 기본 False

        r = await ac.patch(
            f"/transactions/{tid}/essential",
            headers={"Authorization": f"Bearer {token}"},
            json={"essential_override": True},
        )
        assert r.status_code == 204, r.text

        g = await ac.get("/transactions", headers={"Authorization": f"Bearer {token}"})
        row = next(t for t in g.json() if t["id"] == str(tid))
        assert row["essential_override"] is True
        assert row["effective_essential"] is True


async def test_patch_essential_null_resets_to_default(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            tid = await _txn(conn, email, category="housing")  # 기본 True

        await ac.patch(f"/transactions/{tid}/essential",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"essential_override": False})
        r = await ac.patch(f"/transactions/{tid}/essential",
                           headers={"Authorization": f"Bearer {token}"},
                           json={"essential_override": None})
        assert r.status_code == 204, r.text

        g = await ac.get("/transactions", headers={"Authorization": f"Bearer {token}"})
        row = next(t for t in g.json() if t["id"] == str(tid))
        assert row["essential_override"] is None
        assert row["effective_essential"] is True  # 기본값으로 복귀


async def test_patch_essential_404_unknown_id(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.patch(f"/transactions/{uuid4()}/essential",
                           headers={"Authorization": f"Bearer {token}"},
                           json={"essential_override": True})
        assert r.status_code == 404
        assert r.json()["detail"] == "NOT_FOUND"
