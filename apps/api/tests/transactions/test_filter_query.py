import datetime
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-filter-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], email


async def _seed_txn(conn, email, *, txn_date, amount, merchant, category="unknown", override=None):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    user_id = user["id"]
    date_val = datetime.date.fromisoformat(txn_date)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, user_category_override, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, $4, $5, $6, $7, '{}'::jsonb)
        """,
        user_id, date_val, amount, merchant, category, override, str(uuid4()),
    )


async def test_filter_by_month(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(conn, email, txn_date="2026-05-01", amount=1000, merchant="A")
            await _seed_txn(conn, email, txn_date="2026-04-15", amount=2000, merchant="B")

        r = await ac.get(
            "/transactions?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["merchant_raw"] == "A"


async def test_filter_by_category(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(
                conn, email, txn_date="2026-05-01", amount=1, merchant="X", category="coffee"
            )
            await _seed_txn(
                conn, email, txn_date="2026-05-02", amount=2, merchant="Y", category="lunch"
            )
            await _seed_txn(
                conn, email, txn_date="2026-05-03", amount=3, merchant="Z", category="shopping"
            )

        r = await ac.get(
            "/transactions?category=coffee,lunch",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert {t["merchant_raw"] for t in body} == {"X", "Y"}


async def test_filter_by_category_uses_effective_override(test_db_pool):
    """user_category_override 값으로 필터링되는지 (effective_category 기반)."""
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            # auto=unknown, override=groceries → effective=groceries → category=groceries 필터 통과
            await _seed_txn(conn, email, txn_date="2026-05-10", amount=1000,
                            merchant="OVERRIDDEN", category="unknown", override="groceries")
            # auto=coffee, override=NULL → effective=coffee → category=groceries 필터 통과 안 함
            await _seed_txn(conn, email, txn_date="2026-05-11", amount=2000,
                            merchant="STARBUCKS", category="coffee")

        r = await ac.get(
            "/transactions?category=groceries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["merchant_raw"] == "OVERRIDDEN"
        assert body[0]["effective_category"] == "groceries"
        assert body[0]["auto_category"] == "unknown"
        assert body[0]["user_category_override"] == "groceries"


async def test_filter_by_search(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(conn, email, txn_date="2026-05-01", amount=1, merchant="스타벅스 강남")
            await _seed_txn(conn, email, txn_date="2026-05-02", amount=2, merchant="이마트")

        r = await ac.get(
            "/transactions?search=스타벅스",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["merchant_raw"] == "스타벅스 강남"


async def test_pagination(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            for i in range(10):
                await _seed_txn(conn, email, txn_date="2026-05-01", amount=i, merchant=f"M{i}")

        r1 = await ac.get(
            "/transactions?limit=3&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        r2 = await ac.get(
            "/transactions?limit=3&offset=3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert len(r1.json()) == 3
        assert len(r2.json()) == 3
        # No overlap
        ids_1 = {t["id"] for t in r1.json()}
        ids_2 = {t["id"] for t in r2.json()}
        assert ids_1.isdisjoint(ids_2)


async def test_months_endpoint(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(conn, email, txn_date="2026-03-15", amount=1, merchant="A")
            await _seed_txn(conn, email, txn_date="2026-05-10", amount=2, merchant="B")
            await _seed_txn(conn, email, txn_date="2026-05-01", amount=3, merchant="C")

        r = await ac.get(
            "/transactions/months",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body == ["2026-05", "2026-03"]


async def test_months_empty_when_no_transactions(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/transactions/months",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json() == []


async def test_invalid_month_format_returns_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/transactions?month=05-2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "INVALID_MONTH_FORMAT"


async def test_invalid_limit_returns_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/transactions?limit=999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "INVALID_LIMIT"


async def test_negative_offset_returns_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/transactions?offset=-1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "INVALID_LIMIT"


async def test_empty_category_csv_returns_all(test_db_pool):
    """category=,,, (all commas)는 필터 없음과 동일 — 전체 반환."""
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(
                conn, email, txn_date="2026-05-01", amount=1,
                merchant="A", category="coffee",
            )
            await _seed_txn(
                conn, email, txn_date="2026-05-02", amount=2,
                merchant="B", category="lunch",
            )

        r = await ac.get(
            "/transactions?category=,,,",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        # 빈 CSV는 필터 미적용 → 두 행 모두 반환
        assert len(body) == 2
